from pydantic import BaseModel, Field
from enum import StrEnum

# 枚举预签名类型
class PresignedType(StrEnum):
    PUT = "put"
    GET = "get"
    DELETE = "delete"


_STORAGE_REGISTRY: dict[str, type["StorageConfig"]] = {}


class StorageConfig(BaseModel):
    max_size: int = Field(10, description="单文件最大存储（字节）,默认10MB")
    allowed_extensions: list[str] = Field(
        default_factory=list, description="允许的文件扩展名列表，空表示不限制"
    )

    def __init_subclass__(cls, config_type: str | None = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if config_type is not None:
            _STORAGE_REGISTRY[config_type] = cls


class LocalStorage(StorageConfig, config_type="local"):
    base_dir: str | None = Field(None, description="本地存储根目录路径")
    secret_key: str = Field(
        "12345678", description="本地加密密钥，默认值为，默认12345678"
    )


class S3Storage(StorageConfig, config_type="s3"):
    bucket: str = Field(..., description="S3存储桶名称")
    endpoint_url: str | None = Field(
        None, description="S3服务端点URL，如使用AWS S3可不填"
    )
    region: str | None = Field(None, description="S3区域，默认为us-east-1")
    access_key_id: str | None = Field(None, description="S3访问密钥ID")
    secret_access_key: str | None = Field(None, description="S3秘密访问密钥")
    session_token: str | None = Field(None, description="S3会话令牌")


class StorageConfigFactory:
    @staticmethod
    def create(config_type: str, config: dict) -> StorageConfig:
        cls = _STORAGE_REGISTRY.get(config_type)
        if not cls:
            raise ValueError(f"Unknown storage config type: {config_type}")
        return cls.model_validate(config)  # 自动验证 + 实例化
