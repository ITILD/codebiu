from __future__ import annotations

from typing import Protocol, AsyncIterator
import io


class StorageInterface(Protocol):
    """存储接口协议(local 与 s3/minio 等对象存储实现保持一致)

    根目录语义:
    - local: 物理键相对 base_dir 解析(base_dir/key)
    - s3:   物理键相对 bucket 解析(bucket/key)
    """

    async def save(
        self, key: str, data: bytes | io.IOBase | AsyncIterator[bytes]
    ) -> str:
        """保存数据到存储中"""
        ...

    async def load(self, key: str) -> bytes:
        """从存储中加载数据"""
        ...

    def iter_chunks(self, key: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """流式分块读取存储内容(用于大文件下载,避免全量载入内存)"""
        ...

    async def delete(self, key: str) -> bool:
        """删除指定键的数据"""
        ...

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        ...

    async def size(self, key: str) -> int:
        """获取文件大小"""
        ...

    async def list(self, prefix: str = "") -> list[str]:
        """列出指定前缀的所有键"""
        ...

    # ==================== 分片上传(multipart) ====================
    async def create_multipart(
        self, key: str, content_type: str = "application/octet-stream"
    ) -> str:
        """初始化分片上传会话,返回 upload_id"""
        ...

    async def upload_part(
        self, key: str, upload_id: str, part_number: int, data: bytes
    ) -> dict:
        """上传单个分片

        :return: {"part_number": int, "etag": str, "size": int}
        """
        ...

    async def list_parts(self, key: str, upload_id: str) -> list[dict]:
        """查询会话中已上传的分片列表(断点续传)

        :return: [{"part_number": int, "etag": str, "size": int}, ...]
        """
        ...

    async def complete_multipart(
        self,
        key: str,
        upload_id: str,
        parts: list[dict],
        expected_hash: str | None = None,
    ) -> tuple[str, int, str]:
        """按序合并分片为最终文件(内容哈希去重命名)

        :param parts: [{"part_number": int, "etag": str}, ...](按上传顺序)
        :param expected_hash: 调用方声明的内容SHA-256(前端直传场景服务端无法重算,以此归位;
                              本地存储可重算时以真实哈希为准)
        :return: (content_hash, file_size_bytes, final_key)
        """
        ...

    async def abort_multipart(self, key: str, upload_id: str) -> None:
        """取消分片上传会话并清理已上传分片"""
        ...

    # ==================== 预签名直传(direct 模式) ====================
    async def presign_put(
        self,
        key: str,
        upload_id: str | None = None,
        part_number: int | None = None,
        expires: int = 3600,
    ) -> str | None:
        """生成预签名上传URL(前端直传用,不经过服务端)

        :param upload_id: 分片会话ID(为空表示整对象直传)
        :param part_number: 分片号(为空表示整对象直传)
        :return: 预签名URL;存储不支持直传(如local)返回None
        """
        ...

    async def presign_get(
        self, key: str, expires: int = 3600, download_filename: str | None = None
    ) -> str | None:
        """生成预签名下载URL(前端直连下载用,不经过服务端)

        :param download_filename: 下载时的文件名(通过Content-Disposition指定)
        :return: 预签名URL;存储不支持直传(如local)返回None
        """
        ...
