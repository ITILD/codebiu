//! 重排序服务层(对齐 Python module_ai/service/rerank.py)
//!
//! 引擎方案由 model_config 表驱动(model_type=rerank), 引擎缓存键含配置 updated_at,
//! 配置修改后自动重建(仅保留最新一份)。

use std::sync::{Mutex, OnceLock};
use std::time::Instant;

use sea_orm::DatabaseConnection;
use serde_json::{json, Value};

use common::utils::error::AppError;

use crate::dao::model_config as dao;
use crate::do_::entity::model_config as entity;
use crate::do_::rerank::{RerankRequest, RerankResponse};
use crate::utils::rerank::RerankEngine;

/// 单文档文本截断上限(超长文档重排序意义有限且耗费 token)
const MAX_DOC_CHARS: usize = 4000;

/// 引擎缓存: 仅保留最新一份(key="{id}:{updated_at}", 配置变更后旧实例自动丢弃)
fn reranker_cache() -> &'static Mutex<Option<(String, RerankEngine)>> {
    static CACHE: OnceLock<Mutex<Option<(String, RerankEngine)>>> = OnceLock::new();
    CACHE.get_or_init(|| Mutex::new(None))
}

/// 获取重排序引擎(指定 model_id 或取 rerank 类型最优先配置)
///
/// :raises: AppError::not_found 指定的模型配置不存在
/// :raises: AppError::business 配置类型不匹配 / 未配置 rerank 模型 / 方案不支持
pub async fn get_reranker(
    db: &DatabaseConnection,
    model_id: Option<&str>,
) -> Result<RerankEngine, AppError> {
    let config: entity::Model = match model_id {
        Some(id) => {
            let config = dao::get(db, id)
                .await?
                .ok_or_else(|| AppError::not_found(format!("模型配置不存在: {id}")))?;
            if config.model_type != "rerank" {
                return Err(AppError::business(format!("模型配置 {id} 不是 rerank 类型")));
            }
            config
        }
        None => dao::get_first_by_type(db, "rerank", None)
            .await?
            .ok_or_else(|| AppError::business("未配置 rerank 类型模型, 请先在模型配置中添加"))?,
    };
    // 缓存键含 updated_at: 配置变更自动失效重建
    let cache_key = format!("{}:{}", config.id, config.updated_at);
    let mut guard = reranker_cache().lock().expect("重排序引擎缓存锁");
    if let Some((key, engine)) = guard.as_ref() {
        if *key == cache_key {
            return Ok(engine.clone());
        }
    }
    // 构建失败(方案不支持/分数范围非法)统一为业务错误保持接口错误语义
    let engine = RerankEngine::build(
        &config.server_type,
        &config.model,
        config.url.as_deref(),
        config.api_key.as_deref(),
        config.extra.as_ref(),
    )?;
    tracing::info!("重排序引擎已构建: {}/{}", config.server_type, config.model);
    *guard = Some((cache_key, engine.clone()));
    Ok(engine)
}

/// 执行重排序: 返回按相关性降序的 [{node, relevance_score}] 列表(node 保留原文档对象)
pub async fn rerank(
    db: &DatabaseConnection,
    http: &reqwest::Client,
    request: RerankRequest,
) -> Result<RerankResponse, AppError> {
    let start = Instant::now();
    let engine = get_reranker(db, request.model_id.as_deref()).await?;
    // 提取待排序文本(字典按 sort_key 取值, 超长截断)
    let texts: Vec<String> = request
        .documents
        .iter()
        .map(|doc| {
            let raw = match doc {
                Value::String(s) => s.clone(),
                Value::Object(_) => doc
                    .get(&request.sort_key)
                    .map(value_to_text)
                    .unwrap_or_default(),
                _ => String::new(),
            };
            raw.chars().take(MAX_DOC_CHARS).collect()
        })
        .collect();
    if texts.is_empty() {
        return Ok(RerankResponse {
            results: vec![],
            elapsed: elapsed_secs(start),
        });
    }
    let ranked = engine
        .arerank(http, &request.query, &texts, request.top_n.map(|n| n.max(0) as usize))
        .await?;
    // 按返回索引映射回原文档
    let results: Vec<Value> = ranked
        .iter()
        .filter_map(|item| {
            let index = item.get("index").and_then(Value::as_i64)?;
            let node = request.documents.get(index.max(0) as usize)?;
            let score = item
                .get("relevance_score")
                .or_else(|| item.get("score"))
                .and_then(Value::as_f64)
                .unwrap_or(0.0);
            Some(json!({"node": node, "relevance_score": score}))
        })
        .collect();
    Ok(RerankResponse {
        results,
        elapsed: elapsed_secs(start),
    })
}

/// JSON 值转文本(对齐 Python str(doc.get(key, "")): 字符串原样, 其余序列化)
fn value_to_text(value: &Value) -> String {
    match value {
        Value::String(s) => s.clone(),
        Value::Null => String::new(),
        other => other.to_string(),
    }
}

/// 耗时(秒, 保留 3 位小数, 对齐 Python round(time.time() - start, 3))
fn elapsed_secs(start: Instant) -> f64 {
    (start.elapsed().as_secs_f64() * 1000.0).round() / 1000.0
}
