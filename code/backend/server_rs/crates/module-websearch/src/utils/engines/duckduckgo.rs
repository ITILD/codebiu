//! DuckDuckGo 搜索引擎实现(默认引擎,本地直连无需密钥)
//!
//! 使用 html.duckduckgo.com/html/ 端点 POST 查询,
//! 返回经典 HTML 结构,CSS 选择器解析结果块。
//! 时间范围通过 df 参数支持;屏蔽站点为本地过滤。

use async_trait::async_trait;
use scraper::{Html, Selector};

use common::runtime::AppState;
use common::config::dynamic::WebSearchSettings;

use crate::do_::websearch::{DateRange, Engine, SearchResult};
use crate::utils::{build_client, filter_blocked, host_of, net_err, SearchEngine};

/// DDG 轻量 HTML 端点(无 JS 依赖,适合服务端解析)
const SEARCH_URL: &str = "https://html.duckduckgo.com/html/";

/// DateRange -> DDG df 参数映射(df 为空表示不限时间)
fn date_range_param(dr: DateRange) -> Option<&'static str> {
    match dr {
        DateRange::Day => Some("d"),
        DateRange::Week => Some("w"),
        DateRange::Month => Some("m"),
        DateRange::Year => Some("y"),
        DateRange::Any => None,
    }
}

pub struct DuckDuckGoEngine;

#[async_trait]
impl SearchEngine for DuckDuckGoEngine {
    fn name(&self) -> Engine {
        Engine::Duckduckgo
    }

    async fn search(
        &self,
        state: &AppState,
        query: &str,
        limit: usize,
        date_range: DateRange,
        blocked_sites: &[String],
    ) -> Result<Vec<SearchResult>, crate::utils::EngineError> {
        // 超时/代理按当前动态配置(直连引擎,无需密钥)
        let ws: WebSearchSettings = state
            .settings
            .get("websearch")
            .await
            .map_err(|e| crate::utils::EngineError::config(e.to_string()))?;
        let client = build_client(Vec::new(), ws.timeout, ws.proxy.as_deref())?;
        // POST 表单参数: q 查询词, kl 地区, df 时间范围(any 时不传)
        let mut form = vec![("q", query.to_string()), ("kl", "wt-wt".to_string())];
        if let Some(df) = date_range_param(date_range) {
            form.push(("df", df.to_string()));
        }
        // 分页参数 s 为偏移量,单页约25条,一般一页即可满足 limit
        let response = client
            .post(SEARCH_URL)
            .form(&form)
            .send()
            .await
            .map_err(net_err)?;
        let status = response.status();
        if !status.is_success() {
            return Err(crate::utils::EngineError::network(format!(
                "HTTPStatusError: {}",
                status
            )));
        }
        let html_text = response.text().await.map_err(net_err)?;

        let mut results: Vec<SearchResult> = Vec::new();
        let doc = Html::parse_document(&html_text);
        let sel_result = Selector::parse("div.result").expect("静态选择器");
        let sel_link = Selector::parse("a.result__a").expect("静态选择器");
        let sel_snippet = Selector::parse(".result__snippet").expect("静态选择器");
        for item in doc.select(&sel_result) {
            if results.len() >= limit {
                break;
            }
            let Some(link_el) = item.select(&sel_link).next() else {
                continue;
            };
            let title = link_el.text().collect::<String>().trim().to_string();
            let raw_url = link_el.attr("href").unwrap_or("").to_string();
            let url = clean_url(&raw_url);
            // 跳过广告与无效链接(item.get("class", []) 含 result--ad)
            let is_ad = item
                .value()
                .attr("class")
                .map(|c| c.split_whitespace().any(|s| s == "result--ad"))
                .unwrap_or(false);
            if title.is_empty() || url.is_empty() || is_ad {
                continue;
            }
            let description = item
                .select(&sel_snippet)
                .next()
                .map(|el| el.text().collect::<String>().trim().to_string())
                .unwrap_or_default();
            results.push(SearchResult {
                title,
                // source 先于 url 计算(url 所有权随后移入结构体)
                source: host_of(&url),
                url,
                description,
                engine: self.name(),
                published_date: String::new(),
            });
        }
        let results = filter_blocked(results, blocked_sites);
        Ok(results.into_iter().take(limit).collect())
    }
}

/// 清洗 DDG 跳转链接为真实地址
///
/// DDG 返回形如 //duckduckgo.com/l/?uddg=<编码后真实URL>&rut=... 的跳转链
/// :param raw_url: 原始 href
/// :return: 真实 URL(无法解析时原样返回)
fn clean_url(raw_url: &str) -> String {
    if raw_url.is_empty() {
        return String::new();
    }
    let raw_url = if let Some(stripped) = raw_url.strip_prefix("//") {
        format!("https:{stripped}")
    } else {
        raw_url.to_string()
    };
    let Ok(parsed) = url::Url::parse(&raw_url) else {
        return raw_url;
    };
    let hostname = parsed.host_str().unwrap_or("");
    if hostname.contains("duckduckgo.com") && parsed.path() == "/l/" {
        for (key, value) in parsed.query_pairs() {
            if key == "uddg" {
                return value.into_owned();
            }
        }
    }
    raw_url
}
