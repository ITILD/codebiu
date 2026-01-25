from abc import ABC, abstractmethod
from typing import Protocol, AsyncIterator
import io


class StorageInterface(Protocol):
    """存储接口定义"""
    
    async def save(self, key: str, data: bytes | io.IOBase | AsyncIterator[bytes]) -> str:
        """保存数据到存储中"""
        ...
        
    async def load(self, key: str) -> bytes:
        """从存储中加载数据"""
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
    
    async def generate_presigned_url(self, filename: str, content_type: str = 'application/octet-stream', expiration: int = 3600) -> str | None:
        """生成预签名URL"""
        ...
        
    async def upload_with_presigned_url(self, presigned_url: str, data: bytes | io.IOBase | AsyncIterator[bytes]) -> bool:
        """使用预签名URL上传数据"""
        ...
        
    async def download_with_presigned_url(self, presigned_url: str) -> bytes | None:
        """使用预签名URL下载数据"""
        ...
        
    async def delete_with_presigned_url(self, presigned_url: str) -> bool:
        """使用预签名URL删除数据"""
        ...