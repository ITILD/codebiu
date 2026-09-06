from __future__ import annotations

import hashlib
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator
import aiofiles
import io
from module_file.utils.multi_storage.session.interface.strorage_interface import (
    StorageInterface,
)
from module_file.utils.multi_storage.do.storage_config import LocalStorage


class LocalStorageInterface(StorageInterface):
    """本地磁盘存储实现

    物理键相对 base_dir 解析: base_dir/key
    分片上传: 分片暂存 base_dir/.multipart/{upload_id}/{n},完成时合并并按内容哈希归位
    """

    def __init__(self, config: LocalStorage):
        self.config = config
        self.base_dir = Path(config.base_dir).resolve()

    def _multipart_dir(self, upload_id: str) -> Path:
        """分片会话暂存目录(仅允许安全字符,防路径穿越)"""
        if not upload_id or not upload_id.isalnum():
            raise ValueError("非法的分片上传会话ID")
        return self.base_dir / ".multipart" / upload_id

    async def save(
        self, key: str, data: bytes | io.IOBase | AsyncIterator[bytes]
    ) -> str:
        file_path = self.base_dir / key
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(data, bytes):
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(data)
        elif hasattr(data, "read"):  # io.IOBase
            async with aiofiles.open(file_path, "wb") as f:
                while chunk := data.read(8192):
                    await f.write(chunk)
        elif hasattr(data, "__aiter__"):  # AsyncIterator
            async with aiofiles.open(file_path, "wb") as f:
                async for chunk in data:
                    await f.write(chunk)
        else:
            raise TypeError("Unsupported data type for saving")

        return str(file_path)

    async def load(self, key: str) -> bytes:
        file_path = self.base_dir / key
        async with aiofiles.open(file_path, "rb") as f:
            return await f.read()

    async def iter_chunks(self, key: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """流式分块读取本地文件(大文件下载避免全量载入内存)"""
        file_path = self.base_dir / key
        async with aiofiles.open(file_path, "rb") as f:
            while chunk := await f.read(chunk_size):
                yield chunk

    async def delete(self, key: str) -> bool:
        file_path = self.base_dir / key
        try:
            file_path.unlink()
            return True
        except FileNotFoundError:
            return False

    async def exists(self, key: str) -> bool:
        file_path = self.base_dir / key
        return file_path.exists()

    async def size(self, key: str) -> int:
        file_path = self.base_dir / key
        return file_path.stat().st_size

    async def list(self, prefix: str = "") -> list[str]:
        """列出指定前缀的所有键"""
        path_prefix = self.base_dir / prefix
        result = []
        for p in path_prefix.rglob("*"):
            if p.is_file():
                rel_path = p.relative_to(self.base_dir).as_posix()
                result.append(rel_path)
        return sorted(result)

    # ==================== 分片上传(multipart) ====================
    async def create_multipart(
        self, key: str, content_type: str = "application/octet-stream"
    ) -> str:
        upload_id = uuid.uuid4().hex
        self._multipart_dir(upload_id).mkdir(parents=True, exist_ok=True)
        return upload_id

    async def upload_part(
        self, key: str, upload_id: str, part_number: int, data: bytes
    ) -> dict:
        part_file = self._multipart_dir(upload_id) / str(part_number)
        async with aiofiles.open(part_file, "wb") as f:
            await f.write(data)
        return {"part_number": part_number, "etag": str(len(data)), "size": len(data)}

    async def list_parts(self, key: str, upload_id: str) -> list[dict]:
        session_dir = self._multipart_dir(upload_id)
        if not session_dir.exists():
            return []
        parts = []
        for p in sorted(session_dir.iterdir(), key=lambda x: int(x.name)):
            if p.is_file() and p.name.isdigit():
                parts.append(
                    {
                        "part_number": int(p.name),
                        "etag": str(p.stat().st_size),
                        "size": p.stat().st_size,
                    }
                )
        return parts

    async def complete_multipart(
        self,
        key: str,
        upload_id: str,
        parts: list[dict],
        expected_hash: str | None = None,
    ) -> tuple[str, int, str]:
        """按序合并分片,边合并边计算SHA-256,按内容哈希归位(去重)

        本地存储数据面本就在服务端,直接以合并时算出的真实哈希为准
        (expected_hash 仅作对账参考,由 service 层处理不一致场景)
        """
        session_dir = self._multipart_dir(upload_id)
        if not session_dir.exists():
            raise FileNotFoundError(f"分片上传会话不存在: {upload_id}")
        merged = session_dir / "merged"
        hasher = hashlib.sha256()
        total = 0
        async with aiofiles.open(merged, "wb") as out:
            for p in sorted(parts, key=lambda x: int(x["part_number"])):
                part_file = session_dir / str(p["part_number"])
                if not part_file.exists():
                    raise FileNotFoundError(f"分片缺失: {p['part_number']}")
                async with aiofiles.open(part_file, "rb") as f:
                    while chunk := await f.read(1024 * 1024):
                        hasher.update(chunk)
                        total += len(chunk)
                        await out.write(chunk)
        # 按内容哈希生成最终物理键(与直传 uploads/{date}/{hash}{ext} 规则一致)
        ext = Path(key).suffix
        date_str = datetime.now().strftime("%Y%m%d")
        final_key = f"uploads/{date_str}/{hasher.hexdigest()}{ext}"
        final_path = self.base_dir / final_key
        final_path.parent.mkdir(parents=True, exist_ok=True)
        if final_path.exists():
            # 相同内容已存在,复用物理文件(内容哈希去重)
            merged.unlink()
        else:
            merged.replace(final_path)
        shutil.rmtree(session_dir, ignore_errors=True)
        return hasher.hexdigest(), total, final_key

    async def abort_multipart(self, key: str, upload_id: str) -> None:
        session_dir = self._multipart_dir(upload_id)
        shutil.rmtree(session_dir, ignore_errors=True)

    # ==================== 预签名直传(direct 模式) ====================
    async def presign_put(
        self,
        key: str,
        upload_id: str | None = None,
        part_number: int | None = None,
        expires: int = 3600,
    ) -> str | None:
        """本地磁盘不支持浏览器直传(返回None,前端走服务端中转)"""
        return None

    async def presign_get(
        self, key: str, expires: int = 3600, download_filename: str | None = None
    ) -> str | None:
        """本地磁盘不支持浏览器直连下载(返回None,前端走服务端流式代理)"""
        return None
