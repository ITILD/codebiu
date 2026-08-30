from pydantic import BaseModel, Field
# VectorModel
from common.utils.db.orm.vector_model import VectorModel
from module_office.utils.file_parase.do.chunk import Chunk, ContentType, Position
from uuid import uuid4

# 拆分到向量库的内容
class ProjectDocumentChunkBase(VectorModel):
    id: str = Field(primary_key=True,default_factory=lambda: uuid4().hex, description="分块唯一ID")
    sort: int = Field(default=0, description="排序,默认0")
    document_id: str = Field(description="所属文档ID")
    project_id: str = Field(description="所属项目ID")
    content: str = Field(
        description="文本内容,用于BM25分析的文本",
        json_schema_extra={
            "max_length": 8192,
            "enable_analyzer": True,
            "analyzer_params": {"tokenizer": "icu"},  # ICU 会自动处理中英文混合
        },
    )
    source: str = Field(default="", description="来源")
    content_types: list[str] = Field([ContentType.TEXT], description="包含的内容类型")
    position: Position = Field(
        Position(),
        description="位置",
        json_schema_extra={"milvus_dtype": "JSON"},
    )
    # 非标
    metadata: dict[str, str] | None = Field(
        None,
        description="聚合的非标元数据",
        json_schema_extra={"milvus_dtype": "JSON"},
    )
# 拆分到向量库的内容
class ProjectDocumentChunk(ProjectDocumentChunkBase, table=True):
    embedding: list[float] = Field(
        description="向量数据",
        vector_dim=1024,
    )
    # 稀疏向量字段 (由 Milvus 服务端 BM25 Function 自动生成，插入时传 None 即可) TODO 类型确认
    sparse: dict | None = Field(
        default=None,
        description="稀疏向量(BM25自动生成)",
        exclude=True,
        json_schema_extra={"milvus_dtype": "SPARSE_FLOAT_VECTOR"},
    )

# ###########################查询使用

class SearchRequest(BaseModel):
    project_ids: list[str] = Field(description="项目ID列表")
    limit: int = Field(default=2, description="返回的最大结果数,默认2")
    query_content: str = Field(default="", description="用于向量/语义搜索的查询内容")
    query_text: str = Field(default="", description="用于全文/BM25关键词检索的查询文本")
    score_threshold: float = Field(default=0.5, description="Rerank分数阈值(归一化后0~1),低于此值的结果将被过滤")
    enable_rerank: bool = Field(default=False, description="是否启用Rerank精排(深度思考)")
    rerank_limit: int = Field(default=10, description="Rerank精排返回的最大结果数,默认20")


class ProjectDocumentChunkSearchBase(ProjectDocumentChunkBase):
   pass
 

class ProjectDocumentChunkSearchResponse(ProjectDocumentChunkSearchBase):
    score: float = Field(default=1.0, description="RRF融合得分,越大越相关")





if __name__ == "__main__":
    from common.config.db import db_vector
    import asyncio

    async def main():
        await db_vector.create_table(ProjectDocumentChunk, {"embedding": 1024})

    asyncio.run(main())
