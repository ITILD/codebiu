from sqlmodel import Column, DateTime, Field, SQLModel
from sqlalchemy.dialects.postgresql import JSONB
from uuid import uuid4
from datetime import datetime, timezone
from pathlib import Path
from enum import StrEnum
from collections.abc import Awaitable, Callable
from pydantic import BaseModel, Field as PydanticField


class ParseStatus(StrEnum):
    """文档解析状态(对标主流知识库系统的解析进度跟踪)"""

    PENDING = "pending"        # 待解析(刚上传)
    PARSING = "parsing"        # 解析中(任务已派发)
    COMPLETED = "completed"    # 已完成(分块入库成功)
    FAILED = "failed"          # 解析失败(记录失败原因)


class IngestStep(StrEnum):
    """文档入库流水线步骤(扩展方式: 在 INGEST_PIPELINE 追加条目即可, API/前端自动展示)"""

    PARSE = "parse"              # 解析: 文件 → 原始内容块(OCR/文本提取)
    CHUNK = "chunk"              # 拆分chunk: 分块策略识别 + 重分块
    EMBED = "embed"              # 向量化: chunk 向量化并写入向量库
    # ---- 预留步骤(未启用, 不参与进度权重计算, 启用后自动计入) ----
    GRAPH = "graph"              # 图谱化: 知识图谱构建
    TAG = "tag"                  # 标签抽取: 关键词/标签提取
    WEB_MERGE = "web_merge"      # 网络检索合并: 外部检索结果融合入库


class IngestStepState(StrEnum):
    """单个入库步骤的执行状态"""

    PENDING = "pending"        # 未开始
    RUNNING = "running"        # 执行中
    COMPLETED = "completed"    # 已完成
    FAILED = "failed"          # 失败(记录原因)
    SKIPPED = "skipped"        # 跳过(如空文档无需向量化)


def _step(step: IngestStep, name: str, description: str, weight: float, enabled: bool) -> dict:
    """构造流水线步骤定义(内部辅助, 保证注册表条目结构统一)"""
    return {"step": step, "name": name, "description": description,
            "weight": weight, "enabled": enabled}


# 文档入库流水线注册表(有序): enabled 步骤参与总进度权重计算, 预留步骤 weight=0 占位
INGEST_PIPELINE: list[dict] = [
    _step(IngestStep.PARSE, "解析", "OCR/文本提取, 文件转为原始内容块", 40, True),
    _step(IngestStep.CHUNK, "拆分chunk", "分块策略识别与重分块", 20, True),
    _step(IngestStep.EMBED, "向量化", "内容块向量化并写入向量库", 40, True),
    # ---- 预留步骤(实现后把 enabled 改为 True 并配置权重即可) ----
    _step(IngestStep.GRAPH, "图谱化", "知识图谱构建(预留)", 0, False),
    _step(IngestStep.TAG, "标签抽取", "关键词/标签提取(预留)", 0, False),
    _step(IngestStep.WEB_MERGE, "网络检索合并", "外部网络检索结果融合(预留)", 0, False),
]


class IngestStepProgress(SQLModel):
    """单个入库步骤的进度(注册表定义 + 文档实际执行状态合并结果)"""

    step: str = Field(..., description="步骤编码(parse/chunk/embed/graph/tag/web_merge)")
    name: str = Field(..., description="步骤显示名")
    description: str = Field(default="", description="步骤说明")
    enabled: bool = Field(default=True, description="是否已启用(预留步骤为 False)")
    weight: float = Field(default=0, description="总进度权重(未启用步骤为 0)")
    status: str = Field(default=IngestStepState.PENDING, description="执行状态")
    progress: float = Field(default=0, description="步骤内完成百分比 0~100")
    message: str | None = Field(default=None, description="当前阶段描述")
    error: str | None = Field(default=None, description="失败原因")


class DocumentIngestProgress(SQLModel):
    """文档入库步骤与进度响应(GET /{document_id}/progress)"""

    document_id: str = Field(..., description="文档ID")
    parse_status: str = Field(..., description="解析状态(pending/parsing/completed/failed)")
    progress: float = Field(default=0, description="总进度 0~100(按启用步骤权重加权)")
    steps: list[IngestStepProgress] = Field(default_factory=list, description="流水线步骤明细")


def merge_ingest_steps(parse_steps: dict | None) -> list[IngestStepProgress]:
    """流水线注册表与文档已存储的步骤状态合并(未记录的步骤按 pending 展示)"""
    stored = parse_steps or {}
    merged: list[IngestStepProgress] = []
    for spec in INGEST_PIPELINE:
        state = stored.get(spec["step"].value) or {}
        merged.append(IngestStepProgress(
            step=spec["step"].value,
            name=spec["name"],
            description=spec["description"],
            enabled=spec["enabled"],
            weight=spec["weight"],
            status=state.get("status", IngestStepState.PENDING.value),
            progress=float(state.get("progress", 0) or 0),
            message=state.get("message"),
            error=state.get("error"),
        ))
    return merged


def compute_ingest_progress(parse_steps: dict | None) -> float:
    """按启用步骤权重计算总进度(预留步骤不计入; 无记录步骤按 0 计)"""
    total_weight = sum(s["weight"] for s in INGEST_PIPELINE if s["enabled"])
    if total_weight <= 0:
        return 0.0
    stored = parse_steps or {}
    acc = 0.0
    for spec in INGEST_PIPELINE:
        if not spec["enabled"]:
            continue
        state = stored.get(spec["step"].value) or {}
        progress = float(state.get("progress", 0) or 0)
        # completed 兜底 100(防止步骤完成但进度未写满)
        if state.get("status") == IngestStepState.COMPLETED.value:
            progress = 100.0
        acc += spec["weight"] * max(0.0, min(100.0, progress)) / 100.0
    return round(acc / total_weight * 100, 1)


# 入库进度回调类型: async (总进度0~100, 当前阶段描述) -> None(任务队列桥接双写用)
type IngestProgressCallback = Callable[[float, str], Awaitable[None]]


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
        """判断文件扩展名是否允许上传

        :param ext: 文件扩展名(不含点,如 'pdf')
        :return: 允许返回True
        """
        return ext in DocType.ALLOWED_EXTENSIONS

    @staticmethod
    def is_allowed_path(path: str) -> bool:
        """判断文件路径的扩展名是否允许上传

        :param path: 文件路径
        :return: 允许返回True
        """
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
    parse_steps: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
        description="入库步骤进度 JSONB: {step: {status/progress/message/error}}",
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
    parse_steps: dict | None = Field(
        None, description="入库步骤进度 JSONB(由解析流程回写)"
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
    parse_steps: dict = Field(
        default_factory=dict, description="入库步骤进度 JSONB(详见 GET /{id}/progress)"
    )
    uploaded_by: str = Field(..., description="上传者用户ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="最后更新时间")
