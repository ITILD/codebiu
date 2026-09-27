//! LLM 服务层(对齐 Python module_ai/service/llm.py)
//!
//! 职责:
//! - 按模型配置构建调用目标(等价 LangChain build_model, Rust 侧为 HTTP 协议参数)
//! - chat 对话 / embeddings 调用的配置装载(带实例缓存, key="{model_id}_{streaming}")
//! - 模型配置连通性/格式化能力校验(check_config)
//! - 按模型类型运行能力测试并回写 check_result(test_and_persist)
//! - 缓存管理(clear_cache, 配置变更后由调用方触发)

use std::collections::HashMap;
use std::sync::OnceLock;
use std::time::Instant;

use chrono::Utc;
use moka::sync::Cache;
use serde_json::{json, Value};
use sea_orm::DatabaseConnection;

use common::utils::error::AppError;

use crate::dao::model_config as dao;
use crate::do_::entity::model_config as entity;
use crate::do_::llm::{
    capabilities_for, Message, ModelCapabilityTestItem, ModelChatCheckFormat,
    ModelConfigCheckResponse, ModelTestResponse,
};
use crate::do_::model_config::ModelConfigCreateRequest;
use crate::utils::llm::{self, LlmTarget};
use crate::utils::rerank::RerankEngine;
use crate::utils::truncate_body;

/// 模型实例缓存(key="{model_id}_{streaming}", 对齐 Python _model_cache 字典)
static MODEL_CACHE: OnceLock<Cache<String, LlmTarget>> = OnceLock::new();

fn model_cache() -> &'static Cache<String, LlmTarget> {
    MODEL_CACHE.get_or_init(|| Cache::builder().build())
}

/// 16x16 纯红色 PNG(base64 内嵌, 多模态能力测试用, 避免外网图片依赖; 主流模型要求边长>10px)
const VISION_TEST_IMAGE_B64: &str = "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAF0lEQVR4nGP4z8BAEiJN9aiGUQ1DSgMAkPn/Afnh+ngAAAAASUVORK5CYII=";

/// 重排能力测试用例: 语义区分度极大的三级文档(强相关/干扰/明显不相关)
const RERANK_TEST_QUERY: &str = "什么是机器学习?";
const RERANK_TEST_RELEVANT: usize = 0;
const RERANK_TEST_NOISE: usize = 1;
const RERANK_TEST_IRRELEVANT: usize = 2;
const RERANK_TEST_DOC_TEXTS: [&str; 3] = [
    "机器学习是人工智能的一个分支，通过算法让计算机从数据中自动学习模式和规律",
    "机器学习是一种用于开发网站的编程语言",
    "今天天气晴朗，适合外出散步和野餐",
];

/// 单条快捷消息构造
fn msg(role: &str, content: &str) -> Message {
    Message {
        role: role.to_string(),
        content: content.to_string(),
        additional_kwargs: Value::Null,
    }
}

/// 提取模型响应文本(兼容 str/list 形态的 content, 对齐 _content_text)
fn content_text(content: &Value) -> String {
    match content {
        Value::String(s) => s.clone(),
        Value::Array(items) => items
            .iter()
            .map(|part| match part {
                Value::String(s) => s.clone(),
                Value::Object(_) => part
                    .get("text")
                    .and_then(Value::as_str)
                    .unwrap_or_default()
                    .to_string(),
                other => other.to_string(),
            })
            .collect(),
        Value::Null => String::new(),
        other => other.to_string(),
    }
}

/// 格式校验消息(system 描述事实 + user 要求输出 JSON, 等价 LangChain create_agent+response_format)
fn format_check_messages() -> Vec<Message> {
    vec![
        msg(
            "system",
            "There is a person named Bill and he is 100 years old.",
        ),
        msg(
            "user",
            "Extract the person's info from the system message and reply ONLY with a JSON object: {\"name\": string, \"age\": number}. Do not output anything else.",
        ),
    ]
}

/// 从模型响应文本中解析结构化输出(定位首尾大括号之间的 JSON)
fn parse_check_format(text: &str) -> Option<ModelChatCheckFormat> {
    let start = text.find('{')?;
    let end = text.rfind('}')?;
    (end > start).then_some(())?;
    serde_json::from_str(&text[start..=end]).ok()
}

// ############################# 实例装载与缓存 #############################

/// 按模型配置获取调用目标(带缓存; key="{model_id}_{streaming}")
///
/// :return: None 表示配置不存在; Err 表示方案未实现(调用方映射 404, 对齐 Python ValueError)
pub async fn get_llm(
    db: &DatabaseConnection,
    model_id: &str,
    streaming: bool,
) -> Result<Option<LlmTarget>, AppError> {
    let cache_key = format!("{model_id}_{streaming}");
    if let Some(hit) = model_cache().get(&cache_key) {
        return Ok(Some(hit));
    }
    let Some(config) = dao::get(db, model_id).await? else {
        tracing::error!("模型配置不存在: {model_id}");
        return Ok(None);
    };
    let target = LlmTarget::from_entity(&config);
    // 预校验方案可用性: 未实现方案不进缓存(对齐 build_model 的 ValueError)
    if target.model_type == "chat" {
        llm::ensure_chat_supported(&target)?;
    } else if target.model_type == "embeddings" {
        llm::ensure_embeddings_supported(&target)?;
    }
    model_cache().insert(cache_key, target.clone());
    Ok(Some(target))
}

/// 清除模型缓存(model_id 为 None 时清除全部; 前缀匹配对齐 Python startswith)
pub fn clear_cache(model_id: Option<&str>) {
    let cache = model_cache();
    match model_id {
        Some(id) => {
            // moka iter 产出 (Arc<K>, V): 克隆为 String 后逐个失效
            let keys: Vec<String> = cache
                .iter()
                .filter(|(k, _)| k.starts_with(id))
                .map(|(k, _)| k.as_ref().clone())
                .collect();
            for key in keys {
                cache.invalidate(&key);
            }
        }
        None => cache.invalidate_all(),
    }
}

// ############################# 配置校验(check-config) #############################

/// 校验模型配置连通性与输出格式(创建/修改模型配置时使用)
///
/// 模型构建失败(方案未实现/参数缺失)视为校验失败, 不向上抛(对齐 Python check_config)
pub async fn check_config(
    http: &reqwest::Client,
    request: &ModelConfigCreateRequest,
) -> ModelConfigCheckResponse {
    let target = LlmTarget::from_create_request(request);
    check_config_target(http, &target, &request.model_type).await
}

/// 校验模型配置是否有效(按模型配置ID)
pub async fn check_config_by_model_id(
    db: &DatabaseConnection,
    http: &reqwest::Client,
    model_id: &str,
) -> Result<bool, AppError> {
    let Some(config) = dao::get(db, model_id).await? else {
        tracing::error!("模型配置不存在: {model_id}");
        return Ok(false);
    };
    let target = LlmTarget::from_entity(&config);
    let result = check_config_target(http, &target, &config.model_type).await;
    Ok(result.is_valid)
}

/// 校验核心: 按模型类型执行连通性/格式化测试(异常不向上抛, 转为校验失败)
async fn check_config_target(
    http: &reqwest::Client,
    target: &LlmTarget,
    model_type: &str,
) -> ModelConfigCheckResponse {
    let mut resp = ModelConfigCheckResponse::default();
    // 构建失败(方案未实现)返回全 false 默认结果
    let supported = match model_type {
        "chat" => llm::ensure_chat_supported(target),
        "embeddings" => llm::ensure_embeddings_supported(target),
        other => {
            tracing::error!("不支持的模型类型: {other}");
            return resp;
        }
    };
    if let Err(e) = supported {
        tracing::warn!("模型构建失败: {e}");
        return resp;
    }
    match model_type {
        "chat" => {
            // 校验简单问答: 判断回答包含 2
            let ask = [msg("user", "1+1=? only return result number")];
            let content = match llm::chat_once(http, target, &ask).await {
                Ok(c) => c,
                Err(e) => {
                    tracing::warn!("校验模型连通性失败: {e}");
                    resp.is_valid = false;
                    return resp;
                }
            };
            resp.is_valid = content_text(&content).contains("2");
            // 校验 format 格式: 按 schema 返回结构化结果并校验 age==100
            let messages = format_check_messages();
            match llm::chat_once(http, target, &messages).await {
                Ok(c) => match parse_check_format(&content_text(&c)) {
                    Some(fmt) => resp.is_format = fmt.age == 100,
                    None => tracing::warn!("校验format格式失败: 响应中未解析到 JSON 对象"),
                },
                Err(e) => tracing::warn!("校验format格式失败: {e}"),
            }
        }
        "embeddings" => {
            // 校验向量化: 单条文本嵌入向量非空
            let texts = vec!["你好啊".to_string()];
            match llm::embed(http, target, &texts).await {
                Ok(vectors) => {
                    resp.is_valid = vectors.first().map(|v| !v.is_empty()).unwrap_or(false)
                }
                Err(e) => {
                    tracing::warn!("校验向量化模型失败: {e}");
                    resp.is_valid = false;
                }
            }
        }
        other => tracing::error!("不支持的模型类型: {other}"),
    }
    resp
}

// ############################# 能力测试(run_capability_tests / test_and_persist) #############################

/// 按模型类型运行能力测试(未指定时运行该类型全部能力)
///
/// :param config: 模型配置实体
/// :param capabilities: 仅运行指定能力(缺省全部)
/// :return: 各能力测试结果列表(不支持的类型返回空列表)
pub async fn run_capability_tests(
    http: &reqwest::Client,
    config: &entity::Model,
    capabilities: Option<&[String]>,
) -> Result<Vec<ModelCapabilityTestItem>, AppError> {
    let type_key = config.model_type.as_str();
    let all_caps = capabilities_for(type_key);
    let targets: Vec<(&str, &str)> = match capabilities {
        None => all_caps,
        Some(caps) => all_caps
            .into_iter()
            .filter(|(cap, _)| caps.iter().any(|c| c == cap))
            .collect(),
    };
    if targets.is_empty() {
        return Ok(vec![]);
    }
    // chat/embeddings 类构建实例一次复用; 构建失败则全部能力标记失败
    let mut target: Option<LlmTarget> = None;
    if matches!(type_key, "chat" | "embeddings") {
        let built = LlmTarget::from_entity(config);
        let build = if type_key == "chat" {
            llm::ensure_chat_supported(&built)
        } else {
            llm::ensure_embeddings_supported(&built)
        };
        if let Err(e) = build {
            tracing::warn!("模型构建失败: {e}");
            return Ok(targets
                .into_iter()
                .map(|(cap, label)| ModelCapabilityTestItem {
                    capability: cap.to_string(),
                    label: label.to_string(),
                    ok: false,
                    detail: String::new(),
                    error: format!("模型构建失败: {e}"),
                    elapsed: 0.0,
                    suggest: None,
                })
                .collect());
        }
        target = Some(built);
    }
    let mut items = Vec::with_capacity(targets.len());
    for (cap, label) in targets {
        items.push(run_capability(http, cap, label, target.as_ref(), config).await);
    }
    Ok(items)
}

/// 执行单项能力测试并聚合结果(异常不向上抛, 转为失败项)
async fn run_capability(
    http: &reqwest::Client,
    capability: &str,
    label: &str,
    target: Option<&LlmTarget>,
    config: &entity::Model,
) -> ModelCapabilityTestItem {
    let start = Instant::now();
    let mut item = ModelCapabilityTestItem {
        capability: capability.to_string(),
        label: label.to_string(),
        ok: false,
        detail: String::new(),
        error: String::new(),
        elapsed: 0.0,
        suggest: None,
    };
    let outcome: Result<(bool, String, Option<Value>), AppError> = match capability {
        "chat" => test_chat(http, target.expect("chat 能力必带模型实例")).await,
        "structured" => test_structured(http, target.expect("structured 能力必带模型实例")).await,
        "vision" => test_vision(http, target.expect("vision 能力必带模型实例")).await,
        "embedding" => test_embedding(http, target.expect("embedding 能力必带模型实例")).await,
        "rerank" => test_rerank(http, config).await,
        // 语音类引擎(asr/tts/vad/denoise)未在 Rust 服务实现, 按失败项返回
        "asr" | "tts" | "vad" | "denoise" => Err(AppError::business(
            crate::services::voice::VOICE_UNAVAILABLE,
        )),
        _ => Ok((false, String::new(), None)),
    };
    match outcome {
        Ok((ok, detail, suggest)) => {
            item.ok = ok;
            item.detail = detail;
            item.suggest = suggest;
        }
        Err(e) => {
            tracing::warn!("能力测试失败 [{capability}]: {e}");
            item.error = truncate_body(&e.to_string());
        }
    }
    // 耗时保留 2 位小数(对齐 Python round(elapsed, 2))
    item.elapsed = (start.elapsed().as_secs_f64() * 100.0).round() / 100.0;
    item
}

/// 问答能力: 简单算术问答并校验答案包含 2
async fn test_chat(
    http: &reqwest::Client,
    target: &LlmTarget,
) -> Result<(bool, String, Option<Value>), AppError> {
    let ask = [msg("user", "1+1=? only return result number")];
    let content = llm::chat_once(http, target, &ask).await?;
    let text = content_text(&content);
    Ok((text.contains("2"), format!("回答: {}", cut80(&text)), None))
}

/// 结构化输出能力: 按 schema(name/age)返回结构化结果并校验
async fn test_structured(
    http: &reqwest::Client,
    target: &LlmTarget,
) -> Result<(bool, String, Option<Value>), AppError> {
    let messages = format_check_messages();
    let content = llm::chat_once(http, target, &messages).await?;
    let text = content_text(&content);
    let fmt = parse_check_format(&text)
        .ok_or_else(|| AppError::internal("响应中未解析到 JSON 对象"))?;
    Ok((
        fmt.age == 100,
        format!("name={} age={}", fmt.name, fmt.age),
        None,
    ))
}

/// 多模态能力: 发送红色方块图片并校验模型能否识别颜色
async fn test_vision(
    http: &reqwest::Client,
    target: &LlmTarget,
) -> Result<(bool, String, Option<Value>), AppError> {
    let messages = json!([{
        "role": "user",
        "content": [
            {"type": "text", "text": "这张图片中的方块是什么颜色? 只回答中文颜色词"},
            {"type": "image_url", "image_url": {"url": format!("data:image/png;base64,{VISION_TEST_IMAGE_B64}")}},
        ],
    }]);
    let content = llm::chat_once_raw(http, target, messages).await?;
    let text = content_text(&content);
    let lowered = text.to_lowercase();
    let ok = lowered.contains("红") || lowered.contains("red");
    Ok((ok, format!("回答: {}", cut80(&text)), None))
}

/// 向量化能力: 嵌入单条文本并校验向量非空
async fn test_embedding(
    http: &reqwest::Client,
    target: &LlmTarget,
) -> Result<(bool, String, Option<Value>), AppError> {
    let texts = vec!["你好啊".to_string()];
    let vectors = llm::embed(http, target, &texts).await?;
    let dim = vectors.first().map(Vec::len).unwrap_or(0);
    Ok((dim > 0, format!("向量维度: {dim}"), None))
}

/// 重排能力: 用语义区分度极大的文档验证排序, 并自动推断分数范围
///
/// 测试文档刻意选取"强相关 / 干扰 / 明显不相关"三级, 相关文档分数应显著高于
/// 不相关文档; 同时观测全部原始分数的 min/max, 推断模型真实量纲与配置不符时给建议。
async fn test_rerank(
    http: &reqwest::Client,
    config: &entity::Model,
) -> Result<(bool, String, Option<Value>), AppError> {
    let engine = RerankEngine::build(
        &config.server_type,
        &config.model,
        config.url.as_deref(),
        config.api_key.as_deref(),
        config.extra.as_ref(),
    )?;
    let docs: Vec<String> = RERANK_TEST_DOC_TEXTS.iter().map(|s| s.to_string()).collect();
    let ranked = engine.arerank(http, RERANK_TEST_QUERY, &docs, None).await?;
    if ranked.is_empty() {
        return Ok((false, "模型未返回任何排序结果".to_string(), None));
    }
    // index -> (原始分, 归一化分)
    let mut score_map: HashMap<usize, (f64, f64)> = HashMap::new();
    for item in &ranked {
        let Some(index) = item.get("index").and_then(Value::as_i64) else {
            continue;
        };
        let raw = item
            .get("relevance_score")
            .or_else(|| item.get("score"))
            .and_then(Value::as_f64)
            .unwrap_or(0.0);
        score_map.insert(index as usize, (raw, engine.normalize_score(raw)));
    }
    if score_map.len() < RERANK_TEST_DOC_TEXTS.len() {
        return Ok((
            false,
            format!("模型返回结果不完整({}/{})", score_map.len(), RERANK_TEST_DOC_TEXTS.len()),
            None,
        ));
    }
    // 按归一化分数降序得到文档顺序
    let mut order: Vec<usize> = score_map.keys().copied().collect();
    order.sort_by(|a, b| {
        score_map[b]
            .1
            .partial_cmp(&score_map[a].1)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    // 通过标准: 强相关排第一 且 明显不相关排最后
    let ok = order.first() == Some(&RERANK_TEST_RELEVANT)
        && order.last() == Some(&RERANK_TEST_IRRELEVANT);
    let fmt = |i: usize| {
        let (raw, norm) = score_map[&i];
        format!("{raw:.3}→{norm:.3}")
    };
    let mut detail = format!(
        "相关({}) > 干扰({}) > 不相关({}) [原始分→归一化分]",
        fmt(RERANK_TEST_RELEVANT),
        fmt(RERANK_TEST_NOISE),
        fmt(RERANK_TEST_IRRELEVANT)
    );
    if !ok {
        detail += " | 排序不符合预期, 请检查模型可用性";
    }
    // 自动推断分数范围: 观测原始分数 min/max, 与常用量纲比对给建议
    let mut observed_min = f64::MAX;
    let mut observed_max = f64::MIN;
    for (raw, _) in score_map.values() {
        observed_min = observed_min.min(*raw);
        observed_max = observed_max.max(*raw);
    }
    let range_mismatch =
        observed_min < engine.score_min - 1e-6 || observed_max > engine.score_max + 1e-6;
    let mut suggest = json!({
        "observed_min": round_n(observed_min, 4),
        "observed_max": round_n(observed_max, 4),
        "configured_min": engine.score_min,
        "configured_max": engine.score_max,
        "need_fix": range_mismatch,
    });
    if range_mismatch {
        suggest["score_min"] = json!(observed_min);
        suggest["score_max"] = json!(observed_max);
        detail += &format!(
            " | 检测到原始分数范围 [{observed_min:.3}, {observed_max:.3}] 超出配置范围 [{}, {}], 请按建议更新分数范围",
            engine.score_min, engine.score_max
        );
    }
    Ok((ok, detail, Some(suggest)))
}

/// 按模型ID运行能力测试并把结果回写 check_result(前端能力标签常驻展示)
///
/// :raises: AppError::not_found 模型配置不存在(文案对齐 Python ValueError)
pub async fn test_and_persist(
    db: &DatabaseConnection,
    http: &reqwest::Client,
    model_id: &str,
    capability: Option<&str>,
) -> Result<ModelTestResponse, AppError> {
    let Some(config) = dao::get(db, model_id).await? else {
        tracing::error!("模型配置不存在: {model_id}");
        return Err(AppError::not_found(format!("模型配置不存在: {model_id}")));
    };
    let caps: Option<Vec<String>> = capability.map(|c| vec![c.to_string()]);
    let items = run_capability_tests(http, &config, caps.as_deref()).await?;
    let now = Utc::now();
    // 合并回写: 未重测的能力保留历史结果, 已测能力覆盖
    let mut merged = config
        .check_result
        .clone()
        .unwrap_or_else(|| Value::Object(Default::default()));
    if let Some(obj) = merged.as_object_mut() {
        for item in &items {
            obj.insert(
                item.capability.clone(),
                json!({
                    "capability": item.capability,
                    "label": item.label,
                    "ok": item.ok,
                    "detail": item.detail,
                    "error": item.error,
                    "elapsed": item.elapsed,
                    "checked_at": now.to_rfc3339(),
                    "suggest": item.suggest,
                }),
            );
        }
    }
    if !items.is_empty() {
        crate::services::model_config::persist_check_result(db, model_id, merged).await?;
    }
    Ok(ModelTestResponse {
        model_id: model_id.to_string(),
        model_type: config.model_type.clone(),
        capabilities: items,
        checked_at: Some(now),
    })
}

/// 按字符截断到指定长度(对齐 Python text[:n])
fn cut80(text: &str) -> String {
    text.chars().take(80).collect()
}

/// 数值保留 n 位小数(对齐 Python round)
fn round_n(v: f64, digits: u32) -> f64 {
    let factor = 10f64.powi(digits as i32);
    (v * factor).round() / factor
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn 结构化输出解析覆盖混合文本() {
        assert_eq!(
            parse_check_format(r#"{"name": "Bill", "age": 100}"#).map(|f| f.age),
            Some(100)
        );
        assert_eq!(
            parse_check_format(r#"前置说明 {"name":"Bill","age":100} 后缀"#).map(|f| f.age),
            Some(100)
        );
        assert!(parse_check_format("不是 JSON").is_none());
        assert!(parse_check_format("{broken").is_none());
    }

    #[test]
    fn 响应文本提取兼容多形态() {
        assert_eq!(content_text(&json!("直接文本")), "直接文本");
        assert_eq!(content_text(&json!(["a", {"text": "b"}, 1])), "ab1");
        assert_eq!(content_text(&Value::Null), "");
    }

    #[test]
    fn 缓存清理按前缀匹配() {
        let cache = model_cache();
        cache.insert("m1_true".to_string(), test_target());
        cache.insert("other_true".to_string(), test_target());
        clear_cache(Some("m1"));
        assert!(cache.get(&"m1_true".to_string()).is_none());
        assert!(cache.get(&"other_true".to_string()).is_some());
        clear_cache(None);
        assert!(cache.get(&"other_true".to_string()).is_none());
    }

    fn test_target() -> LlmTarget {
        LlmTarget {
            model_type: "chat".to_string(),
            server_type: "openai".to_string(),
            model: "gpt-test".to_string(),
            url: "http://localhost/v1".to_string(),
            api_key: None,
            temperature: 0.7,
            timeout: 60,
            no_think: false,
            out_tokens: 8192,
        }
    }
}
