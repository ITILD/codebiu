from pydantic import BaseModel, Field
from enum import StrEnum


class StorageType(StrEnum):
    LOCAL = "local"
    S3 = "s3"
    # RustFS: S3兼容的开源对象存储,复用S3Storage配置与实现(仅枚举别名)
    RUSTFS = "rustfs"
    # MINIO = "minio"
    # ALIYUN_OSS = "aliyun_oss"


# 枚举预签名类型
class PresignedType(StrEnum):
    PUT = "put"
    GET = "get"
    DELETE = "delete"


_STORAGE_REGISTRY: dict[str, type["StorageConfig"]] = {}


class StorageConfig(BaseModel):
    # 字段名与 config.yaml 的 file_system.max_size 保持一致(MB)
    max_size: int = Field(10, description="单文件最大存储（MB）,默认10MB")
    # 允许的 MIME 类型列表(支持 image/* 通配),空表示不限制
    allowed_extensions: list[str] = Field(
        default_factory=list, description="允许的文件MIME类型列表，空表示不限制"
    )

    def __init_subclass__(cls, config_type: str | None = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if config_type is not None:
            _STORAGE_REGISTRY[config_type] = cls

    # 提供获取最大文件大小的字节表示
    @property
    def max_size_bytes(self) -> int:
        return self.max_size * 1024 * 1024

    def is_mime_allowed(self, mime_type: str | None) -> bool:
        """
        校验 MIME 类型是否在允许列表内
        :param mime_type: 文件 MIME 类型(如 image/png)
        :return: 允许列表为空返回True;否则按精确/通配(image/*)匹配
        """
        if not self.allowed_extensions:
            return True
        if not mime_type:
            return False
        mime = mime_type.lower()
        for pattern in self.allowed_extensions:
            p = pattern.lower()
            # 通配匹配主类型(如 image/* 匹配 image/png)
            if p.endswith("/*") and mime.startswith(p[:-1]):
                return True
            if p == mime:
                return True
        return False


class LocalStorage(StorageConfig, config_type=StorageType.LOCAL):
    base_dir: str | None = Field(None, description="本地存储根目录路径")
    secret_key: str = Field(
        "12345678", description="本地加密密钥，默认值为，默认12345678"
    )


class S3Storage(StorageConfig, config_type=StorageType.S3):
    bucket: str = Field(..., description="S3存储桶名称")
    endpoint_url: str | None = Field(
        None, description="S3服务端点URL，如使用AWS S3可不填"
    )
    region: str | None = Field(None, description="S3区域，默认为us-east-1")
    access_key: str | None = Field(None, description="S3访问密钥ID")
    secret_key: str | None = Field(None, description="S3秘密访问密钥")
    # session_token: str | None = Field(None, description="S3会话令牌")


# RustFS 与 S3 协议完全兼容: 配置类与实现类均复用 S3Storage/S3StorageInterface
# (storage_type: rustfs 与 s3 仅在 file_content.storage_type 记录来源,运行时行为一致)
_STORAGE_REGISTRY[StorageType.RUSTFS] = S3Storage


class StorageConfigFactory:
    @staticmethod
    def create(config_type: str, config: dict) -> StorageConfig:
        cls = _STORAGE_REGISTRY.get(config_type)
        if not cls:
            raise ValueError(f"Unknown storage config type: {config_type}")
        return cls.model_validate(config)  # 自动验证 + 实例化


#  预签名相关配置
class GeneratePresignedUrlRequestBase(BaseModel):
    """
    生成预签名URL的请求模型
    """

    filename: str = Field(..., description="文件名")
    content_type: str = Field(..., description="文件MIME类型")
    # 大小和md5 综合重复校验
    file_size_bytes: int = Field(
        ..., description="Byte 文件字节大小，用于校验文件大小和是否重复上传"
    )
    content_hash: str | None = Field(
        None, description="文件hash校验值，用于校验文件是否重复上传"
    )


class GeneratePresignedResponseBase(BaseModel):
    presigned_url: str | None = Field(None, description="预签名URL")


class GeneratePresignedUploadResponseBase(GeneratePresignedResponseBase):
    """
    生成预签名上传的响应模型
    """

    # 已存在
    is_existing_file: bool = Field(False, description="是否已存在文件")


# 构造的url组成
class PresignedParamsBase(BaseModel):
    expires: int = Field(...)
    method: str = Field(...)
    signature: str = Field(..., min_length=1,description="防伪签名")
