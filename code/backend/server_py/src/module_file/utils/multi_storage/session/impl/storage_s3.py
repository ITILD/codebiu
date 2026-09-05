import aioboto3
from typing import AsyncIterator
import io
from module_file.utils.multi_storage.session.interface.strorage_interface import (
    StorageInterface,
)
from module_file.utils.multi_storage.do.storage_config import S3Storage, PresignedType
from botocore.config import Config as async_config

class S3StorageInterface(StorageInterface):
    """S3存储实现"""

    def __init__(self, config: S3Storage):
        self.config = config
        self.bucket = config.bucket

        # 初始化aioboto3客户端
        self.session = aioboto3.Session()

    def _get_client(self):
        """获取S3客户端"""
        client_kwargs = {
            "service_name": "s3",
            "endpoint_url": self.config.endpoint_url,
            "config": async_config(signature_version="s3v4"),
        }

        # 添加认证信息（如果提供的话）
        if self.config.access_key and self.config.secret_key:
            client_kwargs["aws_access_key_id"] = self.config.access_key
            client_kwargs["aws_secret_access_key"] = self.config.secret_key
            # if self.config.session_token:
            #     client_kwargs["aws_session_token"] = self.config.session_token

        # 添加区域信息（如果提供的话）
        if self.config.region:
            client_kwargs["region_name"] = self.config.region

        return self.session.client(**client_kwargs)

    async def save(
        self, key: str, data: bytes | io.IOBase | AsyncIterator[bytes]
    ) -> str:
        """保存数据到S3存储"""
        async with self._get_client() as client:
            try:
                if isinstance(data, bytes):
                    await client.put_object(Bucket=self.bucket, Key=key, Body=data)
                elif hasattr(data, "read"):  # io.IOBase
                    # 读取IO对象内容
                    content = data.read()
                    if isinstance(content, str):
                        content = content.encode()
                    await client.put_object(Bucket=self.bucket, Key=key, Body=content)
                elif hasattr(data, "__aiter__"):  # AsyncIterator[bytes]
                    # 将异步迭代器内容收集后上传
                    content = bytearray()
                    async for chunk in data:
                        content.extend(chunk)
                    await client.put_object(
                        Bucket=self.bucket, Key=key, Body=bytes(content)
                    )
                else:
                    raise TypeError(f"Unsupported data type: {type(data)}")

                return f"s3://{self.bucket}/{key}"
            except Exception as e:
                raise e

    async def load(self, key: str) -> bytes:
        """从S3存储加载数据"""
        async with self._get_client() as client:
            try:
                response = await client.get_object(Bucket=self.bucket, Key=key)
                content = await response["Body"].read()
                return content
            except client.exceptions.NoSuchKey:
                raise FileNotFoundError(f"Object not found: {key}")
            except Exception as e:
                raise e

    async def delete(self, key: str) -> bool:
        """删除S3存储中的对象"""
        async with self._get_client() as client:
            try:
                await client.delete_object(Bucket=self.bucket, Key=key)
                return True
            except Exception:
                return False

    async def exists(self, key: str) -> bool:
        """检查S3对象是否存在"""
        async with self._get_client() as client:
            try:
                await client.head_object(Bucket=self.bucket, Key=key)
                return True
            except client.exceptions.NoSuchKey:
                return False
            except Exception:
                return False

    async def size(self, key: str) -> int:
        """获取S3对象大小"""
        async with self._get_client() as client:
            try:
                response = await client.head_object(Bucket=self.bucket, Key=key)
                return response["ContentLength"]
            except client.exceptions.NoSuchKey:
                raise FileNotFoundError(f"Object not found: {key}")
            except Exception as e:
                raise e

    async def list(self, prefix: str = "") -> list[str]:
        """列出指定前缀的所有对象"""
        async with self._get_client() as client:
            try:
                paginator = client.get_paginator("list_objects_v2")
                pages = paginator.paginate(Bucket=self.bucket, Prefix=prefix)

                keys = []
                async for page in pages:
                    if "Contents" in page:
                        for obj in page["Contents"]:
                            keys.append(obj["Key"])

                return sorted(keys)
            except Exception as e:
                raise e

    async def generate_presigned_url(
        self,
        method: PresignedType,
        key: str,
        content_type: str = "application/octet-stream",
        expiration: int = 3600,
    ) -> str | None:
        """生成预签名URL"""
        async with self._get_client() as client:
            try:
                params = {"Bucket": self.bucket, "Key": key}
                if method == PresignedType.PUT:
                    # 下载时需要指定Content-Type
                    params.update({"ContentType": content_type})
                    http_method = "put_object"
                elif method == PresignedType.GET:
                    http_method = "get_object"
                elif method == PresignedType.DELETE:
                    http_method = "delete_object"
                # 生成预签名URL
                presigned_url = await client.generate_presigned_url(
                    http_method, Params=params, ExpiresIn=expiration
                )
                return presigned_url
            except Exception as e:
                raise e
