//! 搜索引擎抽象基类 + 通用工具(对齐 Python module_websearch/utils/websearch/base.py)

pub mod engines;

use async_trait::async_trait;
use reqwest::Client;

use crate::do_::websearch::{DateRange, Engine, SearchResult};

/// 模拟浏览器请求头(搜索引擎普遍校验 UA)
pub fn browser_headers() -> Vec<(&'static str, &'static str)> {
    vec![
        (
            "User-Agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        ),
        (
            "Accept",
            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        ),
        ("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8"),
    ]
}

/// API 类引擎通用 JSON 请求头
pub fn json_headers() -> Vec<(&'static str, &'static str)> {
    vec![("Content-Type", "application/json")]
}

/// 引擎侧错误(参数/配置类 → 400; 网络类 → 502)
#[derive(Debug)]
pub enum EngineError {
    /// 配置缺失/参数不合法(对齐 Python ValueError)
    Config(String),
    /// 引擎请求失败(对齐 Python 网络异常 → 502)
    Network(String),
}

impl EngineError {
    pub fn config(msg: impl Into<String>) -> Self {
        EngineError::Config(msg.into())
    }

    pub fn network(msg: impl Into<String>) -> Self {
        EngineError::Network(msg.into())
    }
}

/// 搜索引擎抽象基类: 统一接口与 HTTP 客户端构建
#[async_trait]
pub trait SearchEngine: Send + Sync {
    /// 引擎唯一标识(注册表键,请求参数 engine 使用该值)
    fn name(&self) -> Engine;

    /// 执行搜索
    async fn search(
        &self,
        state: &common::runtime::AppState,
        query: &str,
        limit: usize,
        date_range: DateRange,
        blocked_sites: &[String],
    ) -> Result<Vec<SearchResult>, EngineError>;

    /// 当前配置下引擎是否可用(API Key 等来自动态配置; 无需密钥的引擎默认 true)
    async fn is_configured(&self, state: &common::runtime::AppState) -> bool {
        let _ = state;
        true
    }
}

/// 构建异步 HTTP 客户端(统一超时与代理配置)
///
/// :param extra_headers: 附加请求头(默认合并浏览器 UA)
/// :param timeout: 超时秒数(调用方从动态配置取值传入)
/// :param proxy: 代理地址(None 直连; 调用方从动态配置取值传入)
pub fn build_client(
    extra_headers: Vec<(&str, &str)>,
    timeout: f64,
    proxy: Option<&str>,
) -> Result<Client, EngineError> {
    let mut headers = reqwest::header::HeaderMap::new();
    for (k, v) in browser_headers() {
        headers.insert(
            reqwest::header::HeaderName::from_bytes(k.as_bytes())
                .map_err(|e| EngineError::network(e.to_string()))?,
            reqwest::header::HeaderValue::from_static(v),
        );
    }
    for (k, v) in extra_headers {
        if let (Ok(name), Ok(value)) = (
            reqwest::header::HeaderName::from_bytes(k.as_bytes()),
            reqwest::header::HeaderValue::from_bytes(v.as_bytes()),
        ) {
            headers.insert(name, value);
        }
    }
    let mut builder = Client::builder()
        .default_headers(headers)
        .timeout(std::time::Duration::from_secs_f64(timeout.max(0.1)))
        // 对齐 Python httpx follow_redirects=True
        .redirect(reqwest::redirect::Policy::limited(10));
    if let Some(p) = proxy.filter(|s| !s.is_empty()) {
        let px = reqwest::Proxy::all(p)
            .map_err(|e| EngineError::config(format!("代理配置无效: {e}")))?;
        builder = builder.proxy(px);
    }
    Ok(builder.build().map_err(|e| EngineError::network(e.to_string()))?)
}

/// 提取链接的站点域名(用作来源字段)
pub fn host_of(url: &str) -> String {
    url::Url::parse(url)
        .ok()
        .and_then(|u| u.host_str().map(|h| h.to_string()))
        .unwrap_or_default()
}

/// 归一化域名列表: 去协议头/路径/端口/空白,统一小写并去空去重
///
/// :param sites: 原始域名列表(允许带 https://、路径等冗余)
/// :return: 纯域名列表
pub fn normalize_domains(sites: &[String]) -> Vec<String> {
    let mut normalized: Vec<String> = Vec::new();
    for site in sites {
        let mut host = site.trim().to_lowercase();
        if let Some(pos) = host.find("://") {
            host = host[pos + 3..].to_string();
        }
        host = host.split('/').next().unwrap_or("").to_string();
        host = host.split(':').next().unwrap_or("").to_string();
        // 去掉首部点号与 www. 前缀,保证父域匹配(www.zhihu.com -> zhihu.com)
        host = host.trim_start_matches('.').to_string();
        if let Some(stripped) = host.strip_prefix("www.") {
            host = stripped.to_string();
        }
        if !host.is_empty() && !normalized.contains(&host) {
            normalized.push(host);
        }
    }
    normalized
}

/// 按域名列表过滤结果(父域名匹配,example.com 会屏蔽 a.example.com)
///
/// :param results: 待过滤结果
/// :param blocked_sites: 屏蔽域名列表(未归一化)
/// :return: 过滤后的结果
pub fn filter_blocked(results: Vec<SearchResult>, blocked_sites: &[String]) -> Vec<SearchResult> {
    let domains = normalize_domains(blocked_sites);
    if domains.is_empty() {
        return results;
    }
    results
        .into_iter()
        .filter(|item| {
            let host = host_of(&item.url).to_lowercase();
            !domains
                .iter()
                .any(|d| host == *d || host.ends_with(&format!(".{d}")))
        })
        .collect()
}

/// 统一把 reqwest 错误转成引擎网络错误(502 文案拼装用)
pub fn net_err(e: reqwest::Error) -> EngineError {
    // Python 侧文案为 f"{type(e).__name__}: {e}"; Rust 用错误链摘要近似
    let mut msg = e.to_string();
    if let Some(src) = std::error::Error::source(&e) {
        msg = format!("{msg} ({src})");
    }
    EngineError::network(msg)
}
