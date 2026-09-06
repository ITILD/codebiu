from __future__ import annotations

import aioboto3
from typing import AsyncIterator
import inspect
import io
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from module_file.utils.multi_storage.session.interface.strorage_interface import (
    StorageInterface,
)
from module_file.utils.multi_storage.do.storage_config import S3Storage
from botocore.config import Config as async_config

logger = logging.getLogger(__name__)

# 预签名URL默认有效期(秒)
_PRESIGN_EXPIRES = 3600

class S3StorageInterface(StorageInterface):
    """S3存储实现(rustfs/minio/oss 等S3兼容存储共用)"""

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

    async def ensure_bucket(self) -> None:
        """
        启动时确保桶存在(不存在自动创建)并配置CORS(浏览器直传/直连下载必需)
        :raises: 创建失败时抛出异常(调用方可捕获降级为警告)
        """
        async with self._get_client() as client:
            try:
                await client.head_bucket(Bucket=self.bucket)
            except Exception:
                pass
            else:
                await self._ensure_cors(client)
                return
        # head 失败(通常 404)再尝试创建
        async with self._get_client() as client:
            kwargs = {"Bucket": self.bucket}
            # 非 us-east-1 区域需要显式 LocationConstraint
            if self.config.region and self.config.region != "us-east-1":
                kwargs["CreateBucketConfiguration"] = {
                    "LocationConstraint": self.config.region
                }
            await client.create_bucket(**kwargs)
            logger.info(f"存储桶不存在,已自动创建: {self.bucket}")
            await self._ensure_cors(client)

    async def _ensure_cors(self, client) -> None:
        """配置桶CORS: 允许浏览器预签名直传(PUT)/直连下载(GET)并暴露ETag头"""
        try:
            await client.put_bucket_cors(
                Bucket=self.bucket,
                CORSConfiguration={
                    "CORSRules": [
                        {
                            "AllowedMethods": ["GET", "PUT", "HEAD"],
                            "AllowedOrigins": ["*"],
                            "AllowedHeaders": ["*"],
                            # 前端直传分片后需读取响应ETag做完成对账
                            "ExposeHeaders": ["ETag"],
                            "MaxAgeSeconds": 3600,
                        }
                    ]
                },
            )
            logger.info(f"存储桶CORS已配置(直传/直连下载就绪): {self.bucket}")
        except Exception as e:
            # CORS 配置失败不阻断启动,直传时浏览器会暴露具体错误
            logger.warning(f"存储桶CORS配置失败(直传可能不可用): {e}")

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

    async def iter_chunks(self, key: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """流式分块读取S3对象(大文件下载避免全量载入内存)"""
        async with self._get_client() as client:
            response = await client.get_object(Bucket=self.bucket, Key=key)
            async for chunk in response["Body"].iter_chunks(chunk_size):
                yield chunk

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

    # ==================== 分片上传(S3 Multipart Upload) ====================
    async def create_multipart(
        self, key: str, content_type: str = "application/octet-stream"
    ) -> str:
        """初始化S3分片上传会话"""
        async with self._get_client() as client:
            resp = await client.create_multipart_upload(
                Bucket=self.bucket, Key=key, ContentType=content_type
            )
            return resp["UploadId"]

    async def upload_part(
        self, key: str, upload_id: str, part_number: int, data: bytes
    ) -> dict:
        """上传单个分片(返回S3 ETag用于完成校验)"""
        async with self._get_client() as client:
            resp = await client.upload_part(
                Bucket=self.bucket,
                Key=key,
                UploadId=upload_id,
                PartNumber=part_number,
                Body=data,
            )
            return {"part_number": part_number, "etag": resp["ETag"], "size": len(data)}

    async def list_parts(self, key: str, upload_id: str) -> list[dict]:
        """查询会话中已上传的分片(断点续传)"""
        async with self._get_client() as client:
            resp = await client.list_parts(
                Bucket=self.bucket, Key=key, UploadId=upload_id
            )
            return [
                {
                    "part_number": p["PartNumber"],
                    "etag": p["ETag"],
                    "size": p["Size"],
                }
                for p in resp.get("Parts", [])
            ]

    async def complete_multipart(
        self,
        key: str,
        upload_id: str,
        parts: list[dict],
        expected_hash: str | None = None,
    ) -> tuple[str, int, str]:
        """合并分片并按内容哈希归位

        流程: complete -> head 元数据取大小 -> 按哈希归位(copy+delete,存储端内部复制零流量)
        - expected_hash 提供时直接信任并归位(前端直传场景,服务端不回读数据)
        - 未提供时退化为流式回读计算真实SHA-256(服务端中转场景兜底)
        """
        sorted_parts = sorted(parts, key=lambda p: int(p["part_number"]))
        async with self._get_client() as client:
            await client.complete_multipart_upload(
                Bucket=self.bucket,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={
                    "Parts": [
                        {"PartNumber": p["part_number"], "ETag": p["etag"]}
                        for p in sorted_parts
                    ]
                },
            )
            # 仅元数据请求获取大小(不回读内容,保持直传零流量)
            head = await client.head_object(Bucket=self.bucket, Key=key)
            total = head["ContentLength"]

        if expected_hash:
            # 直传场景: 信任前端声明的SHA-256(完整性由分片对账+S3 ETag保证)
            real_hash, ext_src = expected_hash, key
        else:
            # 兜底: 流式回读计算真实内容哈希
            hasher = hashlib.sha256()
            async with self._get_client() as client:
                resp = await client.get_object(Bucket=self.bucket, Key=key)
                async for chunk in resp["Body"].iter_chunks(1024 * 1024):
                    hasher.update(chunk)
            real_hash, ext_src = hasher.hexdigest(), key
        # 按内容哈希生成最终物理键(与直传 uploads/{date}/{hash}{ext} 规则一致)
        ext = Path(ext_src).suffix
        date_str = datetime.now().strftime("%Y%m%d")
        final_key = f"uploads/{date_str}/{real_hash}{ext}"
        if final_key != key:
            async with self._get_client() as client:
                if await self.exists(final_key):
                    # 相同内容已存在,删除临时对象(内容哈希去重)
                    await client.delete_object(Bucket=self.bucket, Key=key)
                else:
                    await client.copy_object(
                        Bucket=self.bucket,
                        Key=final_key,
                        CopySource={"Bucket": self.bucket, "Key": key},
                    )
                    await client.delete_object(Bucket=self.bucket, Key=key)
        return real_hash, total, final_key

    async def abort_multipart(self, key: str, upload_id: str) -> None:
        """取消分片上传会话(S3侧自动清理已上传分片)"""
        async with self._get_client() as client:
            try:
                await client.abort_multipart_upload(
                    Bucket=self.bucket, Key=key, UploadId=upload_id
                )
            except Exception:
                pass

    # ==================== 预签名直传(direct 模式) ====================
    async def presign_put(
        self,
        key: str,
        upload_id: str | None = None,
        part_number: int | None = None,
        expires: int = _PRESIGN_EXPIRES,
    ) -> str | None:
        """生成预签名上传URL(浏览器直传S3,不经过服务端)"""
        async with self._get_client() as client:
            if upload_id and part_number:
                # 分片直传
                method, params = "upload_part", {
                    "Bucket": self.bucket,
                    "Key": key,
                    "UploadId": upload_id,
                    "PartNumber": part_number,
                }
            else:
                # 整对象直传(小文件单片场景)
                method, params = "put_object", {"Bucket": self.bucket, "Key": key}
            url = client.generate_presigned_url(method, Params=params, ExpiresIn=expires)
            if inspect.iscoroutine(url):
                url = await url
            return url

    async def presign_get(
        self,
        key: str,
        expires: int = _PRESIGN_EXPIRES,
        download_filename: str | None = None,
    ) -> str | None:
        """生成预签名下载URL(浏览器直连S3下载,不经过服务端)"""
        params: dict = {"Bucket": self.bucket, "Key": key}
        if download_filename:
            # RFC 5987 编码文件名,兼容中文/特殊字符
            params["ResponseContentDisposition"] = (
                f"attachment; filename*=UTF-8''{quote(download_filename)}"
            )
        async with self._get_client() as client:
            url = client.generate_presigned_url(
                "get_object", Params=params, ExpiresIn=expires
            )
            if inspect.iscoroutine(url):
                url = await url
            return url
