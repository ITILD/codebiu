from sqlmodel import Column, DateTime, Field, SQLModel
from uuid import uuid4
from datetime import datetime, timezone
from pathlib import Path
from enum import StrEnum
from pydantic import BaseModel, Field as PydanticField


class ParseStatus(StrEnum):
    """文档解析状态(对标主流知识库系统的解析进度跟踪)"""

    PENDING = "pending"        # 待解析(刚上传)
    PARSING = "parsing"        # 解析中(任务已派发)
    COMPLETED = "completed"    # 已完成(分块入库成功)
    FAILED = "failed"          # 解析失败(记录失败原因)


class DocType:
    """RAG文档允许的文件类型

    支持常见文档格式: pdf、docx、xlsx、pptx 等
    """

    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    XLSX = "xlsx"
    PNG = "png"
    JPG = "jpg"
    JPEG = "jpeg"
    TIFF = "tiff"
    MP3 = "mp3"
    WAV = "wav"
    MP4 = "mp4"
    AVI = "avi"
    TXT = "txt"
    MD = "md"
    CSV = "csv"
    PYTHON = "py"
    JAVA = "java"

    # 场景分类，方便分组展示
    DOCUMENT_TYPES = (PDF, DOCX, XLSX, PPTX, TXT, MD, CSV)
    CODE_TYPES = (PYTHON, JAVA)
    IMAGE_TYPES = (PNG, JPG, JPEG, TIFF)
    AUDIO_TYPES = (MP3, WAV)
    VIDEO_TYPES = (MP4, AVI)

    # 允许上传的扩展名集合(不含点)
    ALLOWED_EXTENSIONS = DOCUMENT_TYPES + CODE_TYPES + IMAGE_TYPES + AUDIO_TYPES + VIDEO_TYPES

    # ALLOWED_EXTENSIONS = (PDF, DOCX, XLSX, PPTX, DOC, XLS, PPT, TXT, MD, CSV, MARKDOWN, PNG, JPG, JPEG, TIFF, MP3, WAV, MP4, AVI)
    # 判断文件扩展名是否在允许的集合中 docx、xlsx、pptx 等
    @staticmethod
    def is_allowed_extension(ext: str) -> bool:
        return ext in DocType.ALLOWED_EXTENSIONS

    @staticmethod
    def is_allowed_path(path: str) -> bool:
        ext = Path(path).suffix.lstrip(".").lower()
        return DocType.is_allowed_extension(ext)


class ProjectDocumentBase(SQLModel):
    """项目文档基础模型(不含数据库表配置)"""

    project_id: str = Field(..., max_length=50, index=True, description="所属项目ID")
    name: str = Field(..., max_length=255, description="原始文件名")
    file_extension: str = Field(..., max_length=50, description="文件扩展名(不含点)")
    mime_type: str | None = Field(default=None, max_length=100, description="MIME类型")
    file_size_bytes: int = Field(..., description="文件大小(字节)")
    physical_path: str = Field(
        ..., max_length=500, description="物理存储相对路径(相对 DIR_UPLOAD)"
    )
    description: str | None = Field(
        default=None, max_length=500, description="文档描述"
    )
    parse_status: str = Field(
        default=ParseStatus.PENDING,
        max_length=20,
        index=True,
        description="解析状态: pending/parsing/completed/failed",
    )
    chunk_count: int = Field(default=0, description="解析生成的分块数量")
    error_message: str | None = Field(
        default=None, max_length=1000, description="解析失败原因"
    )


class ProjectDocument(ProjectDocumentBase, table=True):
    """项目文档数据库模型(对应数据库表)"""

    __tablename__ = "project_document"

    id: str = Field(
        default_factory=lambda: uuid4().hex,
        primary_key=True,
        index=True,
        description="唯一标识符",
    )
    uploaded_by: str = Field(..., max_length=50, description="上传者用户ID")
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


class ProjectDocumentCreate(SQLModel):
    """创建项目文档的内部请求模型(由服务层构造，不直接暴露给客户端)"""
    id: str = Field(
        default_factory=lambda: uuid4().hex,
        primary_key=True,
        index=True,
        description="唯一标识符",
    )

    project_id: str = Field(..., max_length=50, description="所属项目ID")
    name: str = Field(..., max_length=255, description="原始文件名")
    file_extension: str = Field(..., max_length=50, description="文件扩展名(不含点)")
    mime_type: str | None = Field(default=None, max_length=100, description="MIME类型")
    file_size_bytes: int = Field(..., description="文件大小(字节)")
    physical_path: str = Field(
        ..., max_length=500, description="物理存储相对路径(相对 DIR_UPLOAD)"
    )
    description: str | None = Field(
        default=None, max_length=500, description="文档描述"
    )
    parse_status: str = Field(
        default=ParseStatus.PENDING, max_length=20, description="解析状态"
    )
    uploaded_by: str = Field(..., max_length=50, description="上传者用户ID")


class ProjectDocumentUpdate(SQLModel):
    """更新项目文档的请求模型"""

    name: str | None = Field(None, max_length=255, description="原始文件名")
    description: str | None = Field(None, max_length=500, description="文档描述")
    parse_status: str | None = Field(None, max_length=20, description="解析状态")
    chunk_count: int | None = Field(None, description="解析生成的分块数量")
    error_message: str | None = Field(
        None, max_length=1000, description="解析失败原因"
    )


class ProjectDocumentResponse(SQLModel):
    """项目文档响应模型"""

    id: str = Field(..., description="唯一标识符")
    project_id: str = Field(..., description="所属项目ID")
    name: str = Field(..., description="原始文件名")
    file_extension: str = Field(..., description="文件扩展名(不含点)")
    mime_type: str | None = Field(default=None, description="MIME类型")
    file_size_bytes: int = Field(..., description="文件大小(字节)")
    physical_path: str = Field(..., description="物理存储相对路径")
    description: str | None = Field(default=None, description="文档描述")
    parse_status: str = Field(default=ParseStatus.PENDING, description="解析状态")
    chunk_count: int = Field(default=0, description="解析生成的分块数量")
    error_message: str | None = Field(default=None, description="解析失败原因")
    uploaded_by: str = Field(..., description="上传者用户ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="最后更新时间")
