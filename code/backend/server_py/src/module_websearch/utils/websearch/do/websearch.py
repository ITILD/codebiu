from enum import StrEnum

from pydantic import BaseModel, Field


class Engine(StrEnum):
    """搜索引擎枚举(新增引擎时在此追加)"""

    DUCKDUCKGO = "duckduckgo"
    TAVILY = "tavily"
    FIRECRAWL = "firecrawl"


class DateRange(StrEnum):
    """搜索结果时间范围限制(各引擎自行映射)"""

    # 不限制
    ANY = "any"
    # 最近一天
    DAY = "day"
    # 最近一周
    WEEK = "week"
    # 最近一月
    MONTH = "month"
    # 最近一年
    YEAR = "year"


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
    # 发布/更新时间(引擎提供时才有)
    published_date: str = Field(default="", description="发布时间(可能为空)")


class SearchRequest(BaseModel):
    """搜索请求体"""

    # 查询信息(句子或关键词)
    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="查询信息(句子或关键词)",
    )
    # 引擎标识(为空使用配置的默认引擎)
    engine: Engine | None = Field(default=None, description="引擎(duckduckgo/tavily/firecrawl,为空用默认)")
    # 返回条数上限(为空使用配置,上限30)
    limit: int | None = Field(
        default=None, ge=1, le=30, description="返回条数上限(为空用配置,上限30)"
    )
    # 时间范围限制(为 any 不限制)
    date_range: DateRange = Field(
        default=DateRange.ANY, description="时间范围限制(any/day/week/month/year)"
    )
    # 屏蔽的站点来源域名列表(支持父域名,如 example.com 会屏蔽其所有子域)
    blocked_sites: list[str] = Field(
        default_factory=list,
        max_length=50,
        description="屏蔽的站点域名列表,如 ['example.com', 'baidu.com']",
    )


class SearchResponse(BaseModel):
    """搜索响应"""

    # 原始查询词
    query: str = Field(description="原始查询词")
    # 实际使用的引擎标识
    engine: Engine = Field(description="实际使用的引擎")
    # 本次生效的时间范围限制
    date_range: DateRange = Field(description="时间范围限制")
    # 本次屏蔽的站点列表
    blocked_sites: list[str] = Field(default_factory=list, description="已屏蔽的站点域名")
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
    # 是否需要 API Key
    requires_api_key: bool = Field(default=False, description="是否需要 API Key")
    # 当前是否可用(API Key 已配置或无需 Key)
    available: bool = Field(default=True, description="当前配置下是否可用")
