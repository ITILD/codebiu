//! 网页搜索服务(对齐 Python module_websearch/service/websearch.py)
//!
//! 引擎注册表管理与搜索分发

use crate::do_::websearch::{DateRange, Engine, EngineInfo, SearchRequest, SearchResponse};
use crate::utils::engines::engine_registry;
use crate::utils::{EngineError, SearchEngine};
use common::config::dynamic::WebSearchSettings;
use common::runtime::AppState;
use common::utils::error::AppError;

/// 网页搜索服务: 引擎注册表管理与搜索分发
pub struct WebSearchService {
    engines: Vec<std::sync::Arc<dyn SearchEngine>>,
}

/// 动态默认引擎名 → Engine 枚举(非法值回退 DuckDuckGo)
fn default_engine(default_name: &str) -> Engine {
    Engine::parse(default_name).unwrap_or_else(|| {
        tracing::warn!("websearch.default_engine 非法值,回退默认引擎: {default_name}");
        Engine::Duckduckgo
    })
}

impl WebSearchService {
    pub fn new() -> Self {
        // 实例化并注册全部引擎(键为引擎唯一标识)
        Self {
            engines: engine_registry(),
        }
    }

    /// 读取当前网页搜索动态配置
    async fn settings(state: &AppState) -> Result<WebSearchSettings, AppError> {
        state.settings.get("websearch").await
    }

    /// 按标识获取引擎(为空返回动态配置的默认引擎)
    ///
    /// :raises: AppError::business 引擎不存在或未配置(缺 API Key)时抛出
    async fn get_engine(
        &self,
        state: &AppState,
        engine: Option<Engine>,
    ) -> Result<std::sync::Arc<dyn SearchEngine>, AppError> {
        let ws = Self::settings(state).await?;
        let name = engine.unwrap_or_else(|| default_engine(&ws.default_engine));
        let instance = self
            .engines
            .iter()
            .find(|e| e.name() == name)
            .cloned()
            .ok_or_else(|| {
                let available = Engine::ALL
                    .iter()
                    .map(|e| e.as_str())
                    .collect::<Vec<_>>()
                    .join(", ");
                AppError::business(format!(
                    "不支持的搜索引擎: {}(可选: {available})",
                    name.as_str()
                ))
            })?;
        if !instance.is_configured(state).await {
            return Err(AppError::business(format!(
                "搜索引擎 {} 未配置 API Key,请在\"系统管理-通用配置\"的网页搜索组中填写",
                name.as_str()
            )));
        }
        Ok(instance)
    }

    /// 列出全部可用引擎元信息(动态默认引擎排前)
    pub async fn list_engines(&self, state: &AppState) -> Result<Vec<EngineInfo>, AppError> {
        let ws = Self::settings(state).await?;
        let default = default_engine(&ws.default_engine);
        let mut infos = Vec::with_capacity(self.engines.len());
        for engine in &self.engines {
            let name = engine.name();
            infos.push(EngineInfo {
                name,
                display_name: name.display_name().to_string(),
                description: name.description().to_string(),
                is_default: name == default,
                requires_api_key: name.requires_api_key(),
                available: engine.is_configured(state).await,
            });
        }
        // 默认引擎置顶
        infos.sort_by_key(|info| !info.is_default);
        Ok(infos)
    }

    /// 执行网页搜索
    ///
    /// :param request: 搜索请求(查询信息/引擎/条数/时间范围/屏蔽站点)
    pub async fn search(&self, state: &AppState, request: &SearchRequest) -> Result<SearchResponse, AppError> {
        let ws = Self::settings(state).await?;
        let query = request.query.trim().to_string();
        if query.is_empty() {
            return Err(AppError::business("查询信息不能为空"));
        }
        let effective_limit = request.limit.unwrap_or(ws.max_results);
        // 条数上限保护(1~30)
        let effective_limit = effective_limit.clamp(1, 30) as usize;
        let date_range = request
            .date_range
            .as_deref()
            .and_then(DateRange::parse)
            .unwrap_or(DateRange::Any);

        let engine_name = request
            .engine
            .as_deref()
            .and_then(Engine::parse);
        let engine = self.get_engine(state, engine_name).await?;
        let results = engine
            .search(state, &query, effective_limit, date_range, &request.blocked_sites)
            .await
            .map_err(|e| match e {
                // 请求参数/配置校验失败 -> 400(需显式转换, 避免被下方网络异常 502 分支捕获)
                EngineError::Config(msg) => AppError::business(msg),
                // 网络类异常(如超时)的 str 可能为空,补充异常类型名便于排查
                EngineError::Network(msg) => {
                    AppError::bad_gateway(format!("搜索引擎请求失败: {msg}"))
                }
            })?;
        let blocked = crate::utils::normalize_domains(&request.blocked_sites);
        tracing::info!(
            "websearch 引擎={} 关键词={query:?} 时间范围={} 屏蔽={blocked:?} 命中={}",
            engine.name().as_str(),
            date_range.as_str(),
            results.len()
        );
        Ok(SearchResponse {
            query,
            engine: engine.name(),
            date_range,
            blocked_sites: blocked,
            total: results.len() as i64,
            results,
        })
    }
}

impl Default for WebSearchService {
    fn default() -> Self {
        Self::new()
    }
}
