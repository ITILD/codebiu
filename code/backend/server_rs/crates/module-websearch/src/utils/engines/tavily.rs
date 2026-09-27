//! Tavily 搜索引擎实现(面向 AI 的搜索 API,需 API Key)
//!
//! 文档: https://docs.tavily.com
//! POST https://api.tavily.com/search,Bearer 鉴权。
//! 原生支持 exclude_domains(屏蔽站点)与 time_range(时间范围)。

use async_trait::async_trait;
use serde_json::json;

use common::config::dynamic::WebSearchSettings;
use common::runtime::AppState;

use crate::do_::websearch::{DateRange, Engine, SearchResult};
use crate::utils::{build_client, filter_blocked, host_of, json_headers, net_err, EngineError, SearchEngine};

/// Tavily 搜索端点
const SEARCH_URL: &str = "https://api.tavily.com/search";

/// DateRange -> Tavily time_range 参数映射(any 不传)
fn date_range_param(dr: DateRange) -> Option<&'static str> {
    match dr {
        DateRange::Day => Some("day"),
        DateRange::Week => Some("week"),
        DateRange::Month => Some("month"),
        DateRange::Year => Some("year"),
        DateRange::Any => None,
    }
}

pub struct TavilyEngine;

/// 判断引擎是否已配置API Key(未配置时在引擎列表中置灰)
pub async fn is_configured(state: &AppState) -> bool {
    let ws: Result<WebSearchSettings, _> = state.settings.get("websearch").await;
    ws.map(|s| !s.tavily.api_key.is_empty()).unwrap_or(false)
}

/// 构建带 Bearer Token 的请求头(Key 未配置时抛出异常)
fn auth_headers(api_key: &str) -> Result<Vec<(&'static str, String)>, EngineError> {
    if api_key.is_empty() {
        return Err(EngineError::config(
            "Tavily API Key 未配置,请在\"系统管理-通用配置\"的网页搜索组中填写",
        ));
    }
    Ok(json_headers()
        .into_iter()
        .map(|(k, v)| (k, v.to_string()))
        .chain(std::iter::once((
            "Authorization",
            format!("Bearer {api_key}"),
        )))
        .collect())
}

#[async_trait]
impl SearchEngine for TavilyEngine {
    fn name(&self) -> Engine {
        Engine::Tavily
    }

    async fn is_configured(&self, state: &AppState) -> bool {
        is_configured(state).await
    }

    async fn search(
        &self,
        state: &AppState,
        query: &str,
        limit: usize,
        date_range: DateRange,
        blocked_sites: &[String],
    ) -> Result<Vec<SearchResult>, EngineError> {
        // 按当前动态配置构建请求(API Key/深度/答案开关/超时/代理即时生效)
        let ws: WebSearchSettings = state
            .settings
            .get("websearch")
            .await
            .map_err(|e| EngineError::config(e.to_string()))?;
        let headers = auth_headers(&ws.tavily.api_key)?;
        let mut payload = json!({
            "query": query,
            "max_results": limit,
            "search_depth": ws.tavily.search_depth,
            "include_answer": ws.tavily.include_answer,
        });
        if let Some(time_range) = date_range_param(date_range) {
            payload["time_range"] = json!(time_range);
        }
        let domains = crate::utils::normalize_domains(blocked_sites);
        if !domains.is_empty() {
            payload["exclude_domains"] = json!(domains);
        }

        let client = build_client(Vec::new(), ws.timeout, ws.proxy.as_deref())?;
        let response = client
            .post(SEARCH_URL)
            .headers(to_header_map(&headers)?)
            .json(&payload)
            .send()
            .await
            .map_err(net_err)?;
        let status = response.status();
        if !status.is_success() {
            return Err(EngineError::network(format!("HTTPStatusError: {status}")));
        }
        let data: serde_json::Value = response.json().await.map_err(net_err)?;

        let mut results: Vec<SearchResult> = Vec::new();
        for item in data
            .get("results")
            .and_then(|v| v.as_array())
            .cloned()
            .unwrap_or_default()
        {
            let url = item.get("url").and_then(|v| v.as_str()).unwrap_or("").to_string();
            let title = item
                .get("title")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .trim()
                .to_string();
            if url.is_empty() || title.is_empty() {
                continue;
            }
            results.push(SearchResult {
                title,
                // source 先于 url 计算(url 所有权随后移入结构体)
                source: host_of(&url),
                url,
                description: item
                    .get("content")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .trim()
                    .to_string(),
                engine: self.name(),
                published_date: item
                    .get("published_date")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string(),
            });
        }
        // Key 已配置给 exclude_domains,这里兜底再做一次本地过滤(极端情况)
        Ok(filter_blocked(results, blocked_sites)
            .into_iter()
            .take(limit)
            .collect())
    }
}

/// 键值对列表转 HeaderMap
pub(crate) fn to_header_map(
    headers: &[(&'static str, String)],
) -> Result<reqwest::header::HeaderMap, EngineError> {
    let mut map = reqwest::header::HeaderMap::new();
    for (k, v) in headers {
        let name = reqwest::header::HeaderName::from_bytes(k.as_bytes())
            .map_err(|e| EngineError::network(e.to_string()))?;
        let value = reqwest::header::HeaderValue::from_bytes(v.as_bytes())
            .map_err(|e| EngineError::network(e.to_string()))?;
        map.insert(name, value);
    }
    Ok(map)
}
