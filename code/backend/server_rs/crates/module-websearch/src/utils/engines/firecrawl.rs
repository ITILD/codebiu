//! Firecrawl 搜索引擎实现(搜索+可爬取,需 API Key)
//!
//! 文档: https://docs.firecrawl.dev
//! POST {api_base}/v1/search,Bearer 鉴权。
//! 时间范围通过 tbs 参数(如 qdr:d)支持;屏蔽站点为本地过滤。

use async_trait::async_trait;
use serde_json::json;

use common::config::dynamic::WebSearchSettings;
use common::runtime::AppState;

use crate::do_::websearch::{DateRange, Engine, SearchResult};
use crate::utils::{build_client, filter_blocked, host_of, json_headers, net_err, EngineError, SearchEngine};
use crate::utils::engines::tavily::to_header_map;

/// DateRange -> Firecrawl tbs 参数映射(google 风格 qdr:*,any 不传)
fn date_range_param(dr: DateRange) -> Option<&'static str> {
    match dr {
        DateRange::Day => Some("qdr:d"),
        DateRange::Week => Some("qdr:w"),
        DateRange::Month => Some("qdr:m"),
        DateRange::Year => Some("qdr:y"),
        DateRange::Any => None,
    }
}

pub struct FirecrawlEngine;

/// 判断引擎是否已配置API Key(未配置时在引擎列表中置灰)
pub async fn is_configured(state: &AppState) -> bool {
    let ws: Result<WebSearchSettings, _> = state.settings.get("websearch").await;
    ws.map(|s| !s.firecrawl.api_key.is_empty()).unwrap_or(false)
}

/// 构建带 Bearer Token 的请求头(Key 未配置时抛出异常)
fn auth_headers(api_key: &str) -> Result<Vec<(&'static str, String)>, EngineError> {
    if api_key.is_empty() {
        return Err(EngineError::config(
            "Firecrawl API Key 未配置,请在\"系统管理-通用配置\"的网页搜索组中填写",
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

/// 拼接搜索端点(api_base 可指向自部署实例)
fn search_url(api_base: &str) -> String {
    format!("{api_base}/v1/search")
}

#[async_trait]
impl SearchEngine for FirecrawlEngine {
    fn name(&self) -> Engine {
        Engine::Firecrawl
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
        // 按当前动态配置构建请求(API Key/端点/超时/代理即时生效)
        let ws: WebSearchSettings = state
            .settings
            .get("websearch")
            .await
            .map_err(|e| EngineError::config(e.to_string()))?;
        let headers = auth_headers(&ws.firecrawl.api_key)?;
        let mut payload = json!({ "query": query, "limit": limit });
        if let Some(tbs) = date_range_param(date_range) {
            payload["tbs"] = json!(tbs);
        }

        let client = build_client(Vec::new(), ws.timeout, ws.proxy.as_deref())?;
        let response = client
            .post(search_url(&ws.firecrawl.api_base))
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

        if data.get("success").and_then(|v| v.as_bool()).unwrap_or(true) == false {
            let err = data
                .get("error")
                .cloned()
                .unwrap_or_else(|| data.clone());
            return Err(EngineError::network(format!("Firecrawl 返回失败: {err}")));
        }

        // 兼容两种返回结构: v1 为列表,新版可能为 {"web": [...]}
        let items = data.get("data").cloned().unwrap_or(serde_json::Value::Null);
        let items: Vec<serde_json::Value> = match items {
            serde_json::Value::Array(arr) => arr,
            serde_json::Value::Object(map) => map
                .get("web")
                .and_then(|v| v.as_array())
                .cloned()
                .unwrap_or_default(),
            _ => Vec::new(),
        };

        let mut results: Vec<SearchResult> = Vec::new();
        for item in items {
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
                    .get("description")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .trim()
                    .to_string(),
                engine: self.name(),
                published_date: item
                    .get("publishedDate")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string(),
            });
        }
        // Firecrawl 暂不支持 exclude 参数,统一本地过滤
        Ok(filter_blocked(results, blocked_sites)
            .into_iter()
            .take(limit)
            .collect())
    }
}
