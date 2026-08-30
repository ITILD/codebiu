"""分块中间对象定义

ChunkedItem 设计为 ProjectDocumentChunk 的基类结构，包含分块后的内容与位置信息。
不含 DB 相关字段 (id, sort, document_id, project_id, embedding, sparse)，
这些字段在入库时由 parse_document 赋值。

ChunkStrategyEnum 从 module_office.do.document_chunk 迁移至此,
作为分块工具模块的自有策略定义。
"""

from enum import StrEnum

from pydantic import BaseModel, Field

from module_office.utils.file_parase.do.chunk import Chunk, ContentType, Position


class ChunkStrategyEnum(StrEnum):
    """分块策略枚举"""

    GENERAL = "general"
    TABLES = "tables"
    CODE = "code"


class ChunkStrategyRecommendation(BaseModel):
    """大模型推荐的分块策略"""

    strategy: ChunkStrategyEnum = Field(
        default=ChunkStrategyEnum.GENERAL,
        description="""
        分块策略对应规则如下：
        - `general`: 通用分块：按分隔符和长度切分，适合大多数普通文档、报告、新闻。
        - `tables`: 表格分块：专门处理包含表格的文档，适合数据报告、统计资料等。
        - `code`: 代码分块：按 Python/Java 类、函数和方法边界拆分源代码。
        """,
    )
    reason: str = Field(
        default="默认分块策略",
        description="简洁推荐该策略的简短理由，例如：'文档包含大量问答对，适合QA策略'",
    )


class ChunkConfig(BaseModel):
    """分块配置参数"""

    chunk_token_num: int = Field(default=512, description="单块最大 token 数")
    overlapped_percent: int = Field(default=10, description="块间重叠百分比 0-99")
    delimiter: str = Field(default="\n", description="分段分隔符")
    context_token_num: int = Field(
        default=128,
        description="独立内容(表格/图片等)附带上下文的 token 数, 0 表示不附带",
    )
    split_oversized_row_by_cell: bool = Field(
        default=True, description="是否将超大行拆分成多个单元格"
    )


class ChunkedItem(BaseModel):
    """
    分块结果项 - 中间对象

    结构与 ProjectDocumentChunk 的内容字段对齐，可作为其基类:
    ProjectDocumentChunk 在此基础上增加 id/sort/document_id/project_id/embedding/sparse。

    保留原始 chunk 的位置信息聚合结果，用于后续精确定位。
    """

    content: str = Field(description="文本内容,用于BM25分析的文本")
    content_types: list[str] = Field(
        default_factory=lambda: [ContentType.TEXT], description="包含的内容类型"
    )
    position: Position = Field(default_factory=Position, description="聚合的位置信息")
    source: str = Field(default="", description="来源")
    metadata: dict[str, str] | None = Field(None, description="聚合的非标元数据")


def merge_positions(positions: list[Position]) -> Position:
    """将多个 Position 聚合为一个

    - page: 取最小页码
    - bbox: 同页的 bbox 合并为外接矩形; 跨页时仅保留首页 bbox
    - heading_level: 取最小值 (最高层级标题)
    - time_range: 取最早起始时间
    - text_range: 不聚合, 保留首个
    """
    if not positions:
        return Position()

    pages = [p.page for p in positions if p.page is not None]
    heading_levels = [p.heading_level for p in positions if p.heading_level is not None]
    time_ranges = [p.time_range for p in positions if p.time_range is not None]
    text_ranges = [p.text_range for p in positions if p.text_range is not None]

    # bbox 聚合: 仅合并同页 bbox
    bbox_result: list[float] | None = None
    page_groups: dict[int, list[list[float]]] = {}
    for p in positions:
        if p.bbox is not None and p.page is not None:
            page_groups.setdefault(p.page, []).append(p.bbox)
    if page_groups:
        first_page = min(page_groups.keys())
        bboxes = page_groups[first_page]
        if len(bboxes) == 1:
            bbox_result = bboxes[0]
        else:
            # 合并为外接矩形 [l, t, r, b]
            bbox_result = [
                min(b[0] for b in bboxes),  # l
                min(b[1] for b in bboxes),  # t
                max(b[2] for b in bboxes),  # r
                max(b[3] for b in bboxes),  # b
            ]

    return Position(
        page=min(pages) if pages else None,
        text_range=text_ranges[0] if text_ranges else None,
        time_range=time_ranges[0] if time_ranges else None,
        bbox=bbox_result,
        heading_level=min(heading_levels) if heading_levels else None,
    )


def merge_metadata(metas: list[dict | None]) -> dict[str, str] | None:
    """合并多个 metadata dict, 后者不覆盖已有 key"""
    result: dict[str, str] = {}
    for meta in metas:
        if not meta:
            continue
        for k, v in meta.items():
            if k not in result and v is not None:
                result[k] = str(v)
    return result if result else None


def build_item(content: str, sources: list[Chunk]) -> ChunkedItem:
    """从合并后的文本和来源 Chunk 列表构建 ChunkedItem"""
    if not sources:
        return ChunkedItem(content=content)

    content_types = list({s.content_type.value for s in sources if s.content_type})
    if not content_types:
        content_types = [ContentType.TEXT]

    positions = [s.position for s in sources if s.position]
    position = merge_positions(positions) if positions else Position()

    metas = [s.metadata for s in sources]
    metadata = merge_metadata(metas)

    source = ""
    if sources[0].metadata:
        source = sources[0].metadata.get("source", "")

    return ChunkedItem(
        content=content,
        content_types=content_types,
        position=position,
        source=source,
        metadata=metadata,
    )
