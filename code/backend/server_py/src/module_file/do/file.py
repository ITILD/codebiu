from sqlmodel import Column, DateTime, Field, SQLModel
from uuid import uuid4
from datetime import datetime, timezone


class FileBase(SQLModel):
    """
    文件基础模型（不含数据库表配置）
    """
    file_name: str = Field(..., max_length=255, description="文件名")
    file_path: str = Field(..., max_length=500, description="文件存储路径")
    file_size: int = Field(..., description="文件大小（字节）")
    file_type: str = Field(..., max_length=100, description="文件类型/扩展名")
    mime_type: str = Field(..., max_length=100, description="MIME类型")
    md5: str = Field(..., max_length=32, description="文件MD5哈希值")
    description: str | None = Field(default=None, max_length=500, description="文件描述")
    is_active: bool = Field(default=True, description="是否有效")
    uploaded_by: str | None = Field(default=None, description="上传者ID")


class File(FileBase, table=True):
    """
    文件数据库模型（对应数据库表）
    """
    id: str = Field(
        default_factory=lambda: uuid4().hex,
        primary_key=True,  # 主键
        index=True,  # 索引
        description="唯一标识符",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
        description="创建时间",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            onupdate=lambda: datetime.now(timezone.utc),  # 自动更新
            nullable=False,  # 不允许为空
        ),
        description="最后更新时间",
    )


class FileCreate(FileBase):
    """
    创建文件记录的请求模型
    """
    pass


class FileUpdate(SQLModel):
    """
    更新文件记录的请求模型
    """
    description: str | None = Field(default=None, max_length=500, description="文件描述")
    is_active: bool | None = Field(default=None, description="是否有效")