from enum import StrEnum

from pydantic import BaseModel, Field


class Engine(StrEnum):
    """搜索引擎枚举(新增引擎时在此追加)"""

    DUCKDUCKGO = "duckduckgo"
    BING = "bing"


class SearchResult(BaseModel):
    """单条搜索结果"""

    # 结果标题
    title: str = Field(description="结果标题")
    # 结果链接(已清洗为真实地址)
    url: str = Field(description="结果链接")
    # 摘要描述
    description: str = Field(default="", description="摘要描述")
    # 来源站点域名
    source: str = Field(default="", description="来源站点域名")
    # 产出该结果的引擎标识
    engine: Engine = Field(description="来源引擎")


class SearchResponse(BaseModel):
    """搜索响应"""

    # 原始查询词
    query: str = Field(description="原始查询词")
    # 实际使用的引擎标识
    engine: Engine = Field(description="实际使用的引擎")
    # 返回条数
    total: int = Field(description="返回条数")
    # 搜索结果列表
    results: list[SearchResult] = Field(default_factory=list, description="搜索结果列表")


class EngineInfo(BaseModel):
    """搜索引擎元信息"""

    # 引擎唯一标识(请求参数 engine 使用该值)
    name: Engine = Field(description="引擎唯一标识")
    # 展示名称
    display_name: str = Field(description="展示名称")
    # 引擎说明
    description: str = Field(default="", description="引擎说明")
    # 是否为默认引擎
    is_default: bool = Field(default=False, description="是否为默认引擎")
