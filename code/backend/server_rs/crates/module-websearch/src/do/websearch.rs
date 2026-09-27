//! 网页搜索请求/响应 DO 层(对齐 Python module_websearch/utils/websearch/do/websearch.py)

use serde::{Deserialize, Serialize};

/// 搜索引擎枚举(新增引擎时在此追加)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Engine {
    Duckduckgo,
    Tavily,
    Firecrawl,
}

impl Engine {
    pub const ALL: [Engine; 3] = [Engine::Duckduckgo, Engine::Tavily, Engine::Firecrawl];

    /// 引擎唯一标识(序列化/日志展示用小写字符串)
    pub fn as_str(&self) -> &'static str {
        match self {
            Engine::Duckduckgo => "duckduckgo",
            Engine::Tavily => "tavily",
            Engine::Firecrawl => "firecrawl",
        }
    }

    /// 字符串解析(非法值返回 None)
    pub fn parse(s: &str) -> Option<Self> {
        match s {
            "duckduckgo" => Some(Engine::Duckduckgo),
            "tavily" => Some(Engine::Tavily),
            "firecrawl" => Some(Engine::Firecrawl),
            _ => None,
        }
    }

    /// 展示名称
    pub fn display_name(&self) -> &'static str {
        match self {
            Engine::Duckduckgo => "DuckDuckGo",
            Engine::Tavily => "Tavily",
            Engine::Firecrawl => "Firecrawl",
        }
    }

    /// 引擎说明
    pub fn description(&self) -> &'static str {
        match self {
            Engine::Duckduckgo => "默认引擎,本地直连无需密钥,支持时间范围与屏蔽站点",
            Engine::Tavily => "AI 搜索 API,原生支持屏蔽站点与时间范围,需 API Key",
            Engine::Firecrawl => "搜索+网页抓取 API,支持时间范围,需 API Key",
        }
    }

    /// 是否需要 API Key
    pub fn requires_api_key(&self) -> bool {
        !matches!(self, Engine::Duckduckgo)
    }
}

/// 搜索结果时间范围限制(各引擎自行映射)
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DateRange {
    /// 不限制
    #[default]
    Any,
    /// 最近一天
    Day,
    /// 最近一周
    Week,
    /// 最近一月
    Month,
    /// 最近一年
    Year,
}

impl DateRange {
    pub fn as_str(&self) -> &'static str {
        match self {
            DateRange::Any => "any",
            DateRange::Day => "day",
            DateRange::Week => "week",
            DateRange::Month => "month",
            DateRange::Year => "year",
        }
    }

    pub fn parse(s: &str) -> Option<Self> {
        match s {
            "any" => Some(DateRange::Any),
            "day" => Some(DateRange::Day),
            "week" => Some(DateRange::Week),
            "month" => Some(DateRange::Month),
            "year" => Some(DateRange::Year),
            _ => None,
        }
    }
}

/// 单条搜索结果
#[derive(Debug, Clone, Serialize)]
pub struct SearchResult {
    /// 结果标题
    pub title: String,
    /// 结果链接(已清洗为真实地址)
    pub url: String,
    /// 摘要描述
    #[serde(default)]
    pub description: String,
    /// 来源站点域名
    #[serde(default)]
    pub source: String,
    /// 产出该结果的引擎标识
    pub engine: Engine,
    /// 发布/更新时间(引擎提供时才有)
    #[serde(default)]
    pub published_date: String,
}

/// 搜索请求体
#[derive(Debug, Deserialize)]
pub struct SearchRequest {
    /// 查询信息(句子或关键词)
    pub query: String,
    /// 引擎标识(为空使用配置的默认引擎)
    #[serde(default)]
    pub engine: Option<String>,
    /// 返回条数上限(为空使用配置,上限30)
    #[serde(default)]
    pub limit: Option<i64>,
    /// 时间范围限制(为 any 不限制)
    #[serde(default)]
    pub date_range: Option<String>,
    /// 屏蔽的站点来源域名列表(支持父域名,如 example.com 会屏蔽其所有子域)
    #[serde(default)]
    pub blocked_sites: Vec<String>,
}

/// 搜索响应
#[derive(Debug, Serialize)]
pub struct SearchResponse {
    /// 原始查询词
    pub query: String,
    /// 实际使用的引擎标识
    pub engine: Engine,
    /// 本次生效的时间范围限制
    pub date_range: DateRange,
    /// 本次屏蔽的站点列表
    pub blocked_sites: Vec<String>,
    /// 返回条数
    pub total: i64,
    /// 搜索结果列表
    pub results: Vec<SearchResult>,
}

/// 搜索引擎元信息
#[derive(Debug, Serialize)]
pub struct EngineInfo {
    /// 引擎唯一标识(请求参数 engine 使用该值)
    pub name: Engine,
    /// 展示名称
    pub display_name: String,
    /// 引擎说明
    pub description: String,
    /// 是否为默认引擎
    pub is_default: bool,
    /// 是否需要 API Key
    pub requires_api_key: bool,
    /// 当前是否可用(API Key 已配置或无需 Key)
    pub available: bool,
}
