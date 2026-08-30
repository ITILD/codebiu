from enum import StrEnum
from pydantic import BaseModel, Field


class ContentType(StrEnum):
    """内容类型枚举"""
    # 考虑细分目录
    TEXT = "text"
    # 标题
    TITLE = "title"
    # 文件链接
    IMAGE = "image"
    # 图片描述内容
    IMAGE_CONTENT = "image_content"
    AUDIO = "audio"
    VIDEO = "video"
    TABLE_SHEET = "table_sheet"
    # 分为完整表格table（小于等于1000字）
    TABLE = "table"
    # 非完整表格（大于1000字）分成表头table_header和表格内容table_content
    TABLE_HEADER = "table_header"
    TABLE_CONTENT = "table_content"
    # Python/Java 等源代码。代码块由专用解析器按符号边界生成，
    # 后续必须走 code 分块策略，不能与普通文本合并。
    CODE = "code"
    # # 公式
    # FORMULA = "formula"
    # # 图表
    # CHART = "chart"


class Position(BaseModel):
    """位置模型"""

    page: int | None = Field(None, description="页码")
    text_range: list[int] | None = Field(
        None, description="文本起始结束的行列数组[start_row,start_col,end_row,end_col]"
    )
    time_range: list[float] | None = Field(None, description="音视频时间[start_time,end_time]")
    bbox: list[float] | None = Field(None, description="PDF/图片边界框[l,t,r,b]")
    heading_level: int | None = Field(
        None, description="语义标题级别(1=h1,2=h2...);标题元素与sheet页有值,正文为None"
    )


class Chunk(BaseModel):
    """分块模型"""

    content: str | None = Field(None, description="文本内容")
    # 标准元数据
    content_type: ContentType = Field(ContentType.TEXT, description="内容类型")
    position: Position = Field(Position(), description="位置")
    # 非标
    metadata: dict[str, str] | None = Field(None, description="非标元数据")