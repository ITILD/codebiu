from pydantic import BaseModel
from sqlmodel import Column, DateTime, Field, SQLModel
from uuid import uuid4
from datetime import datetime, timezone
from module_file.utils.multi_storage.do.storage_config import (
    PresignedParamsBase,
    GeneratePresignedUrlRequestBase,
    GeneratePresignedResponseBase,
    GeneratePresignedUploadResponseBase,
)
from module_file.utils.multi_storage.do.storage_config import StorageType
from common.enum.task import TaskStatus


# 文件内容元数据（仅用于文件）
class FileContentBase(SQLModel):
    """文件内容元数据，全局唯一，基于内容哈希"""

    content_hash: str | None = Field(
        default=None,
        primary_key=True,
        max_length=64,
        description="内容哈希(仅文件),强制唯一",
    )
    physical_storage: str | None = Field(
        default=None,
        max_length=500,
        # 使用content_hash作为物理存储文件名，避免文件名有编码等问题
        description="物理存储相对位置(仅文件，如 相对bucket位置/key 或 相对位置 data/file.bin)",
    )
    file_size_bytes: int | None = Field(
        default=None, description="文件大小(字节，仅文件)"
    )
    # 引用计数
    ref_count: int = Field(default=0, description="引用计数(仅文件),上传成功后增加1")
    # === 存储类型字段 ===
    storage_type: StorageType | None = Field(
        default=StorageType.LOCAL, description="存储类型(仅文件)"
    )
    # 状态
    content_status: TaskStatus | None = Field(
        default=TaskStatus.PENDING,
        max_length=50,
        description="文件状态(仅文件) status: 进行中/完成/失败",
    )


class FileContent(FileContentBase, table=True):
    """
    文件内容元数据数据库模型
    """

    __tablename__ = "file_content"


class FileContentCreate(FileContentBase):
    """
    文件内容元数据数据库模型
    """


class FileContentUpdate(FileContentBase):
    """
    文件内容元数据数据库模型
    """


class FileEntryBase(SQLModel):
    """
    文件系统条目基础模型(文件/目录通用)
    """

    # === 关联字段 ===
    pid: str | None = Field(None, description="父级ID")

    # === 核心字段 ===
    name: str = Field(..., max_length=255, description="条目名称(文件名或目录名)")
    logical_path: str = Field(
        ..., max_length=2000, description="逻辑路径(用户视角的文件系统路径)"
    )

    is_directory: bool = Field(default=False, description="是否为目录")
    # === 逻辑关联字段 ===
    content_hash: str | None = Field(
        default=None, max_length=64, description="内容哈希(仅文件)"
    )
    file_size_bytes: int | None = Field(
        default=None, description="文件大小(字节，仅文件)"
    )
    # === 文件元数据字段 ===
    file_extension: str | None = Field(
        default=None, max_length=50, description="文件扩展名(不含点，仅文件)"
    )
    mime_type: str | None = Field(
        default=None, max_length=100, description="MIME类型(仅文件)"
    )

    # === 业务字段 ===
    description: str | None = Field(
        default=None, max_length=500, description="条目描述"
    )
    is_active: bool = Field(default=True, description="是否有效(软删除标志)")
    user_id: str | None = Field(default=None, description="拥有者用户ID")
    group_id: str | None = Field(default=None, description="拥有者组ID")
    entry_status: TaskStatus | None = Field(
        default=TaskStatus.SUCCESS,
        max_length=50,
        description="文件状态(仅文件) status: 进行中/完成/失败",
    )


class FileEntry(FileEntryBase, table=True):
    """
    文件系统条目数据库模型
    """

    __tablename__ = "file_entry"
    # === 主键 ===
    id: str = Field(
        default_factory=lambda: uuid4().hex,
        primary_key=True,  # 主键
        index=True,  # 索引
        description="唯一标识符",
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


class FileEntryUpdate(FileEntryBase):
    """
    更新文件系统条目的请求模型
    """

    name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = Field(default=None)
    # 以下路径字段仅由服务层在重命名/移动时维护,不对前端开放
    pid: str | None = Field(default=None, description="父级ID(移动时使用)")
    logical_path: str | None = Field(
        default=None, max_length=2000, description="逻辑路径(重命名/移动时同步)"
    )


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


class GeneratePresignedUrlRequest(GeneratePresignedUrlRequestBase):
    """
    生成预签名URL的请求模型
    """

    domain: str = Field("main", description="业务域")


class GeneratePresignedUploadResponse(GeneratePresignedUploadResponseBase):
    """
    生成预签名上传的响应模型
    """

    content_status: TaskStatus | None = Field(
        default=None,
        max_length=50,
        description="文件状态(仅文件) status: 进行中/完成/失败",
    )


class GeneratePresignedDownloadResponse(GeneratePresignedResponseBase):
    """
    生成预签名下载的响应模型
    """

    pass


class PresignedUploadParams(PresignedParamsBase):
    """预签名上传的参数"""

    pass
class PresignedDownloadParams(PresignedParamsBase):
    """预签名下载的参数"""

    pass


class UploadSuccessResponse(BaseModel):
    file_id: str = Field(..., description="文件ID")


# # 文件上传成功通知
# class FileUploadSuccessNotificationRequest(BaseModel):
#     """
#     文件上传成功通知模型
#     """

#     pid: str | None = Field(default=None, description="父条目ID")
#     name: str = Field(..., max_length=255, description="文件名")
#     content_hash: str = Field(..., max_length=64, description="内容哈希")
#     physical_storage: str = Field(..., max_length=500, description="物理存储相对位置")
#     file_size_bytes: int = Field(..., description="文件大小(字节)")
#     file_extension: str | None = Field(
#         default=None, max_length=50, description="文件扩展名(不含点，仅文件)"
#     )


class FileEntryWithContent(BaseModel):
    """
    文件条目 + 内容元数据的联合视图（非数据库模型，仅用于 API 返回）
    """
    # --- 来自 FileEntry ---
    id: str
    pid: str | None = None
    name: str
    logical_path: str
    is_directory: bool
    content_hash: str | None = None
    file_size_bytes: int | None = None
    file_extension: str | None = None
    mime_type: str | None = None
    description: str | None = None
    is_active: bool = True
    user_id: str | None = None
    group_id: str | None = None
    entry_status: TaskStatus | None = None
    created_at: datetime
    updated_at: datetime

    # --- 来自 FileContent ---
    physical_storage: str | None = None
    ref_count: int | None = None
    storage_type: StorageType | None = None
    content_status: TaskStatus | None = None

    @classmethod
    def from_models(
        cls,
        entry: FileEntry,
        content: FileContent
    ) -> "FileEntryWithContent":
        """从 FileEntry 和可选的 FileContent 构造实例"""
        data = entry.model_dump()
        if content:
            data.update(content.model_dump())
        return cls(**data)


class StorageStats(BaseModel):
    """
    存储统计信息(管理视图)
    """

    storage_type: str = Field(..., description="当前生效的存储类型(local/s3/rustfs)")
    entry_total: int = Field(0, description="逻辑条目总数(含目录)")
    file_total: int = Field(0, description="文件条目数")
    folder_total: int = Field(0, description="目录条目数")
    content_total: int = Field(0, description="物理内容记录数(按内容哈希去重后)")
    used_bytes: int = Field(0, description="物理存储总占用(字节,去重后)")


class MigrateRequest(BaseModel):
    """
    存储迁移请求(把旧存储的物理内容搬运到新存储,逻辑条目不变)
    """

    from_type: StorageType = Field(..., description="源存储类型(旧数据所在存储)")
    to_type: StorageType = Field(..., description="目标存储类型(迁移目的地)")