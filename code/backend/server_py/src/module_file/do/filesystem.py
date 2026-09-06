from pydantic import BaseModel, Field
from sqlmodel import Column, DateTime, Field, SQLModel
from sqlalchemy import JSON
from uuid import uuid4
from datetime import datetime, timezone
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
    tags: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False, server_default="[]"),
        description="关键词标签组(默认空,可手动输入或由RAG智能提取)",
    )
    source_module: str | None = Field(
        default=None,
        max_length=50,
        description="来源模块key(rag/avatar等业务模块标记, NULL=文件管理自有条目); 创建时从父目录继承",
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
    tags: list[str] | None = Field(default=None, description="关键词标签组")
    is_active: bool | None = Field(default=None)
    # 以下路径字段仅由服务层在重命名/移动时维护,不对前端开放
    pid: str | None = Field(default=None, description="父级ID(移动时使用)")
    logical_path: str | None = Field(
        default=None, max_length=2000, description="逻辑路径(重命名/移动时同步)"
    )
    # 来源模块仅由服务层在创建时从父目录继承,不对前端开放
    source_module: str | None = Field(default=None, max_length=50)


# ==================== 分片上传(multipart)模型 ====================
class MultipartInitRequest(BaseModel):
    """初始化分片上传请求"""

    filename: str = Field(..., max_length=255, description="文件名")
    content_type: str | None = Field(None, description="文件MIME类型")
    file_size_bytes: int = Field(..., ge=1, description="文件总大小(字节)")
    content_hash: str = Field(
        ..., min_length=32, max_length=64, description="文件内容SHA-256(前端计算)"
    )
    pid: str | None = Field(None, description="父目录ID(为空上传到根目录)")
    description: str | None = Field(None, max_length=500, description="文件描述")


class MultipartPartInfo(BaseModel):
    """分片信息"""

    part_number: int = Field(..., ge=1, le=10000, description="分片号(从1开始)")
    etag: str = Field("", description="分片ETag(S3返回,合并校验用)")
    size: int = Field(0, ge=0, description="分片大小(字节)")


class MultipartInitResponse(BaseModel):
    """初始化分片上传响应"""

    is_existing: bool = Field(False, description="内容已存在(秒传,直接建条目)")
    upload_id: str | None = Field(
        None, description="分片上传会话凭证(签名token,秒传时为None)"
    )
    part_size: int = Field(..., description="建议分片大小(字节,最后一片可小于该值)")
    mode: str = Field(
        "proxy",
        description="上传模式: direct=预签名直传S3(前端直连) / proxy=服务端中转(local)",
    )
    part_urls: list[str] | None = Field(
        None,
        description="direct模式专用: 每片的预签名上传URL(下标=分片号-1);proxy模式为None",
    )


class MultipartCompleteRequest(BaseModel):
    """完成分片上传请求"""

    filename: str = Field(..., max_length=255, description="文件名")
    pid: str | None = Field(None, description="父目录ID(为空上传到根目录)")
    description: str | None = Field(None, max_length=500, description="文件描述")
    file_size_bytes: int | None = Field(None, description="文件总大小(完整性校验)")
    parts: list[MultipartPartInfo] = Field(..., min_length=1, description="已上传分片列表")


class UploadModeResponse(BaseModel):
    """上传模式查询响应(前端上传前获取,决定直传/中转策略)"""

    mode: str = Field(..., description="上传模式: direct=预签名直传 / proxy=服务端中转")
    part_size: int = Field(..., description="分片大小(字节)")
    max_size: int = Field(..., description="proxy模式下小文件直传上限(MB)")


class EntryCreateRequest(BaseModel):
    """内容已存在(秒传)时创建文件条目请求"""

    name: str = Field(..., max_length=255, description="文件名")
    pid: str | None = Field(None, description="父目录ID(为空上传到根目录)")
    content_hash: str = Field(..., min_length=32, max_length=64, description="内容SHA-256")
    file_size_bytes: int = Field(..., ge=1, description="文件大小(字节)")
    mime_type: str | None = Field(None, max_length=100, description="MIME类型")
    description: str | None = Field(None, max_length=500, description="文件描述")


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
    tags: list[str] | None = None
    is_active: bool = True
    user_id: str | None = None
    group_id: str | None = None
    entry_status: TaskStatus | None = None
    source_module: str | None = None
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


class FileEntryDetail(FileEntryWithContent):
    """
    条目详情视图(详情按钮用): 条目+内容元数据+上传用户名
    """

    owner_name: str | None = Field(None, description="上传用户名(昵称优先,其次用户名)")

    @classmethod
    def from_entry_with_content(
        cls, info: FileEntryWithContent, owner_name: str | None = None
    ) -> "FileEntryDetail":
        """从联合视图构造详情(tags 归一化为空数组)"""
        data = info.model_dump()
        data["tags"] = data.get("tags") or []
        return cls(**data, owner_name=owner_name)


class BatchDeleteRequest(BaseModel):
    """批量删除请求(文件与目录混选,目录递归删除)"""

    entry_ids: list[str] = Field(..., min_length=1, description="条目ID列表")


class BatchDeleteItemError(BaseModel):
    """批量删除单项失败信息"""

    id: str = Field(..., description="条目ID")
    error: str = Field(..., description="失败原因")


class BatchDeleteResult(BaseModel):
    """批量删除结果"""

    deleted: int = Field(0, description="成功删除数")
    failed: list[BatchDeleteItemError] = Field(default_factory=list, description="失败列表")


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