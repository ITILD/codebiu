from pydantic import BaseModel, Field
from typing import Literal
from enum import StrEnum


class ChunkStrategyEnum(StrEnum):
    """分块策略枚举 """
    GENERAL = "general"
    # QA = "qa"
    # BOOK = "book"
    # LAWS = "laws"
    # SEMANTIC = "semantic"
    # SEPARATOR = "separator"
    TABLES = "tables"

class ChunkStrategyRecommendation(BaseModel):
    """大模型推荐的分块策略"""
    preset_id: ChunkStrategyEnum = Field(default=ChunkStrategyEnum.GENERAL,description="""
    分块策略对应规则如下：
    - `general`: 通用分块：按分隔符和长度切分，适合大多数普通文档、报告、新闻。
    - `qa`: 问答分块：优先抽取问题-回答结构，适合 FAQ、题库、问答手册。
    - `tables`: 表格分块：专门处理包含表格的文档，适合数据报告、统计资料等。
    """)
    
    reason: str = Field(description="推荐该策略的简短理由，例如：'文档包含大量问答对，适合QA策略'")

# # 扁平化的描述字典
# CHUNK_PRESET_DESCRIPTIONS: dict[str, str] = {
#     ChunkStrategyEnum.GENERAL: "通用分块：按分隔符和长度切分，适合大多数普通文档、报告、新闻。",
#     ChunkStrategyEnum.QA: "问答分块：优先抽取问题-回答结构，适合 FAQ、题库、问答手册。",
#     ChunkStrategyEnum.BOOK: "书籍分块：强化章节标题识别并做层级合并，适合教材、手册、长章节文档。",
#     ChunkStrategyEnum.LAWS: "法规分块：按法条层级组织与合并，适合法律法规、制度规范类文本。",
#     ChunkStrategyEnum.SEMANTIC: "语义分块：利用嵌入和聚类算法进行语义切分，并自动增强标题上下文。",
#     ChunkStrategyEnum.SEPARATOR: "严格分隔：命中分隔符即切分，仅超长片段内部继续按长度切分。",
# }
