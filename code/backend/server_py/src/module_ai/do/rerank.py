"""重排序(Rerank) 数据传输对象"""
from pydantic import BaseModel, Field


class RerankRequest(BaseModel):
    """重排序请求"""

    query: str = Field(..., description="检索查询文本")
    documents: list[str | dict] = Field(
        ..., description="待排序文档列表(字符串 或 含 sort_key 字段的字典)"
    )
    model_id: str | None = Field(
        None, description="模型配置ID或标识名称(缺省取 rerank 类型默认配置)"
    )
    top_n: int | None = Field(None, ge=1, description="返回前 N 条结果(缺省返回全部)")
    sort_key: str = Field("content", description="documents 为字典时提取文本的字段名")


class RerankResponse(BaseModel):
    """重排序响应(按相关性降序)"""

    results: list[dict] = Field(
        default_factory=list, description="排序结果 [{node: 原文档, relevance_score: 相关性分数}]"
    )
    elapsed: float = Field(0.0, description="耗时(秒)")
