# src/models/schemas.py
from enum import Enum
from typing import  Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from annotated_types import MaxLen
from typing import Annotated


class ProcessingStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"


class FileType(str, Enum):
    # DOC = ".doc"
    # XLS = ".xls"
    # PPT = ".ppt"
    PDF = ".pdf"
    DOCX = ".docx"
    PPTX = ".pptx"
    XLSX = ".xlsx"
    PNG = ".png"
    JPG = ".jpg"
    JPEG = ".jpeg"
    TIFF = ".tiff"
    MP3 = ".mp3"
    WAV = ".wav"
    MP4 = ".mp4"
    AVI = ".avi"
    TXT = ".txt"
    MD = ".md"
    MARKDOWN = ".markdown"
    CSV = ".csv"
    PYTHON = ".py"
    JAVA = ".java"

    @classmethod
    def is_document(cls, ext: str) -> bool:
        """判断是否为支持解析的文本文档类型"""
        return ext.lower() in [
            cls.PDF.value,
            cls.DOCX.value,
            cls.PPTX.value,
            cls.XLSX.value,
            cls.MD.value,
            cls.MARKDOWN.value,
            cls.CSV.value,
            cls.TXT.value,
            cls.PYTHON.value,
            cls.JAVA.value,
        ]

    @classmethod
    def is_code(cls, ext: str) -> bool:
        """判断是否为支持语义拆分的源代码文件。"""
        return ext.lower() in [cls.PYTHON.value, cls.JAVA.value]
    @classmethod
    def is_image(cls, ext: str) -> bool:
        """判断是否为图片文件"""
        return ext.lower() in [cls.PNG.value, cls.JPG.value, cls.JPEG.value, cls.TIFF.value]

    @classmethod
    def is_audio(cls, ext: str) -> bool:
        """判断是否为音频文件"""
        return ext.lower() in [cls.MP3.value, cls.WAV.value]

    @classmethod
    def is_video(cls, ext: str) -> bool:
        """判断是否为视频文件"""
        return ext.lower() in [cls.MP4.value, cls.AVI.value]

    @classmethod
    def is_audio_video(cls, ext: str) -> bool:
        """复用上面的方法"""
        return cls.is_audio(ext) or cls.is_video(ext)


# ================= 细粒度内容块模型 =================


class ContentBlock(BaseModel):
    block_type: Literal["text", "heading", "table", "image", "audio", "video"]
    content: str = Field(..., description="核心内容：文本/表格Markdown，图片则为Base64编码")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="附加信息，如图片路径(path)、表格行列数等"
    )


# =======================================================


class TextExtractionResult(BaseModel):
    status: ProcessingStatus
    blocks: list[ContentBlock] = Field(default_factory=list, description="解析出的内容块列表")
    error_message: str | None = None
    processing_time: Optional[float] = None


class ImageExtractionResult(BaseModel):
    status: ProcessingStatus
    extracted_count: int = 0
    image_paths: list[str] = []
    error_message: str | None = None


class AudioVideoResult(BaseModel):
    status: ProcessingStatus
    transcript: str = ""  # <--- 必须有这个字段来存放提取出的文本
    language: str | None = None
    duration: float | None = None
    processing_time: float = 0.0
    error_message: str | None = None


class FileProcessingResult(BaseModel):
    file_name: str
    file_path: str
    file_type: str
    file_size: int
    text_result: TextExtractionResult | None = Field(default=None, description="文本提取结果")
    image_result: Optional[ImageExtractionResult] = None
    av_result: Optional[AudioVideoResult] = None
    overall_status: ProcessingStatus = ProcessingStatus.PENDING


class BatchProcessingResult(BaseModel):
    total_files: int = Field(description="总文件数")
    successful_files: int = Field(default=0, description="成功处理文件数")
    failed_files: int = Field(default=0, description="失败处理文件数")
    results: list[FileProcessingResult] = Field(default=[], description="文件处理结果列表")


class TextChunk(BaseModel):
    """文本分块"""

    chunk_id: str = Field(..., description="分块唯一标识，格式：文件名_block索引_chunk序号")
    content: str = Field(..., description="分块文本内容")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="来源文件、页码、块类型等元数据"
    )
    # 可选：直接携带向量化所需信息
    # embedding: Optional[list[float]] = None


class ChunkedResult(BaseModel):
    """单个文件的分块结果"""

    file_name: str
    file_path: str
    chunks: list[TextChunk] = Field(default_factory=list)
    error_message: str | None = None
    media_type: str | None = Field(
        default=None, 
        description="媒体类型，如 'video' 或 'audio'。普通文档为 None。"
    )

class BatchChunkedResult(BaseModel):
    """批量文件分块结果"""

    total_files: int
    chunked_files: int = 0
    total_chunks: int = 0
    results: list[ChunkedResult] = Field(default_factory=list)


class MilvusRecord(BaseModel):
    chunk_id: str
    content: str
    embedding: list[float]
    metadata: Dict[str, Any]
