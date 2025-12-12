from sqlmodel import Column, DateTime, Field, SQLModel
from uuid import uuid4
from datetime import datetime, timezone
from enum import Enum


class StorageType(str, Enum):
    LOCAL = "local"
    S3 = "s3"
    RUSTFS = "rustfs"
    MINIO = "minio"
    ALIYUN_OSS = "aliyun_oss"


class FileEntryBase(SQLModel):
    """
    文件系统条目基础模型(文件/目录通用)
    """

    # === 核心字段 ===
    name: str = Field(..., max_length=255, description="条目名称(文件名或目录名)")
    logical_path: str = Field(
        ..., max_length=2000, description="逻辑路径(用户视角的文件系统路径)"
    )

    # === 类型标识 ===
    is_directory: bool = Field(default=False, description="是否为目录")
    storage_type: StorageType | None = Field(
        default=StorageType.LOCAL, description="存储类型(仅文件)"
    )

    # === 文件特有字段 ===
    physical_storage: str | None = Field(
        default=None,
        max_length=500,
        description="物理存储位置(仅文件，如 s3://bucket/key 或 相对位置 data/file.bin)",
    )
    file_size_bytes: int | None = Field(
        default=None, description="文件大小(字节，仅文件)"
    )
    file_extension: str | None = Field(
        default=None, max_length=50, description="文件扩展名(不含点，仅文件)"
    )
    mime_type: str | None = Field(
        default=None, max_length=100, description="MIME类型(仅文件)"
    )
    content_hash: str | None = Field(
        default=None, max_length=64, description="内容哈希(仅文件)"
    )

    # === 元数据字段 ===
    description: str | None = Field(
        default=None, max_length=500, description="条目描述"
    )
    is_active: bool = Field(default=True, description="是否有效(软删除标志)")
    owner_user_id: str | None = Field(default=None, description="拥有者用户ID")
    owner_group_id: str | None = Field(default=None, description="拥有者组ID")


class FileEntry(FileEntryBase, table=True):
    """
    文件系统条目数据库模型
    """

    # === 主键 ===
    id: str = Field(
        default_factory=lambda: uuid4().hex,
        primary_key=True,
        index=True,
        description="全局唯一标识符",
    )

    # === 关联字段 ===
    pid: str | None = Field(
        default=None,
        description="父条目ID",
    )

    # === 时间戳 ===
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
        description="创建时间",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            onupdate=lambda: datetime.now(timezone.utc),
            nullable=False,
        ),
        description="最后更新时间",
    )


class FileEntryCreate(FileEntryBase):
    """
    创建文件系统条目的请求模型
    """

    pid: str | None = Field(default=None, description="父条目ID")


class FileEntryUpdate(SQLModel):
    """
    更新文件系统条目的请求模型
    """

    name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = Field(default=None)
    # 注意：路径相关字段通常不允许直接修改


class FileEntryInfo(SQLModel):
    """
    文件系统条目信息响应模型
    """

    id: str
    name: str
    logical_path: str
    is_directory: bool
    storage_type: str | None
    file_size_bytes: int | None
    file_extension: str | None
    created_at: datetime
    updated_at: datetime
    owner_user_id: str | None


# 获取或插入多层 非Sqlmodel
