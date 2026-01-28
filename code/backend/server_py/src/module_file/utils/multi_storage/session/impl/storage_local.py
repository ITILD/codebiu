import hashlib
import hmac
import time
import urllib.parse
from pathlib import Path
from typing import AsyncIterator
import aiofiles
import io
from module_file.utils.multi_storage.session.interface.strorage_interface import (
    StorageInterface,
)
from module_file.utils.multi_storage.do.storage_config import (
    LocalStorage,
    PresignedType,
)
from urllib.parse import urlencode


class LocalStorageInterface(StorageInterface):
    def __init__(self, config: LocalStorage):
        self.config = config
        self.base_dir = Path(config.base_dir).resolve()

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
        path_prefix = self.base_dir / prefix
        result = []
        for p in path_prefix.rglob("*"):
            if p.is_file():
                rel_path = p.relative_to(self.base_dir).as_posix()
                result.append(rel_path)
        return sorted(result)

    async def generate_presigned_url(
        self,
        method: PresignedType,
        # 文件路径
        key: str,
        content_type: str = "application/octet-stream",
        expiration: int = 3600,
    ) -> str | None:
        """生成预签名URL，格式为"""
        # 模拟真实s3格式
        expire_time = int(time.time()) + expiration
        # 使用HMAC SHA256生成签名
        signature = await self.generate_signature(key, method.value, expire_time)
        # 构建URL
        params = urlencode(
            {
                "expires": expire_time,
                "method": method.lower(),
                "signature": signature,
            }
        )
        url_path = f"/{key}?{params}"
        return url_path

    async def validate_and_extract_params(
        self, presigned_url: str
    ) -> tuple[str, str] | None:
        """验证预签名URL并提取参数"""
        parsed = urllib.parse.urlparse(presigned_url)
        key = urllib.parse.unquote(parsed.path.lstrip("/"))

        params = dict(urllib.parse.parse_qsl(parsed.query))
        expires = int(params.get("expires", 0))
        method = params.get("method", "get")
        signature = params.get("signature")

        # 检查URL是否过期
        if time.time() > expires:
            return None

        # 验证签名
        expected_signature = await self.generate_signature(key, method, expires)
        # 验证签名是否匹配
        if not hmac.compare_digest(signature, expected_signature):
            return None

        return key, method

    # 生成验证签名
    async def generate_signature(
        self,
        key: str,
        method: str,
        expires: int,
    ) -> str:
        """生成验证签名"""
        sign_content = f"{key}:{method}:{expires}"
        return hmac.new(
            self.config.secret_key.encode("utf-8"),
            sign_content.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    async def upload_with_presigned_url(
        self, presigned_url: str, data: bytes | io.IOBase | AsyncIterator[bytes]
    ) -> bool:
        """使用预签名URL上传数据"""
        result = await self.validate_and_extract_params(presigned_url)
        if result is None:
            return False

        key, method = result
        if method.lower() != "put":
            return False

        try:
            await self.save(key, data)
            return True
        except Exception:
            return False

    async def download_with_presigned_url(self, presigned_url: str) -> bytes | None:
        """使用预签名URL下载数据"""
        result = await self.validate_and_extract_params(presigned_url)
        if result is None:
            return None

        key, method = result
        if method.lower() != "get":
            return None

        try:
            return await self.load(key)
        except Exception:
            return None

    async def delete_with_presigned_url(self, presigned_url: str) -> bool:
        """使用预签名URL删除数据"""
        result = await self.validate_and_extract_params(presigned_url)
        if result is None:
            return False

        key, method = result
        if method.lower() != "delete":
            return False

        try:
            return await self.delete(key)
        except Exception:
            return False
