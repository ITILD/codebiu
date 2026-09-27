//! 重排序引擎(等价 Python utils/llm/rerank/{interface,impl/*}.py)
//!
//! 三种协议:
//! - dashscope: gte-rerank 系官方接口(`input`/`parameters` 包裹, bge 系 parameters 顶层平铺)
//! - ollama: jina 兼容 shim(`query`/`documents` 顶层, `parameters` 兜底兼容)
//! - vllm/openai: vLLM `/v1/rerank` jina 兼容协议(query/documents 顶层传)
//!
//! 分数量纲由模型配置 extra.score_min/score_max 声明(默认 0~1),
//! normalize_score 统一归一化到 [0,1] 后供上游按 0~1 语义做阈值过滤。

use std::time::Duration;

use serde_json::{json, Value};

use common::utils::error::AppError;

/// DashScope 官方重排序接口
const DASHSCOPE_RERANK_URL: &str =
    "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank";
/// Ollama jina 兼容 shim 默认地址
const OLLAMA_RERANK_URL: &str = "http://localhost:11434/api/rerank";
/// vLLM /v1/rerank 默认地址
const VLLM_RERANK_URL: &str = "http://localhost:10002/v1/rerank";

/// 重排序引擎(协议由 server_type 决定, 构建失败即业务错误)
#[derive(Debug, Clone)]
pub struct RerankEngine {
    pub server_type: String,
    pub model: String,
    pub url: String,
    pub api_key: Option<String>,
    pub score_min: f64,
    pub score_max: f64,
}

impl RerankEngine {
    /// 从模型配置构建引擎(url 缺省按方案回落官方/本地默认; 不支持的方案报业务错误)
    ///
    /// 分数范围从 extra.score_min/score_max 读取, 非法时回退 0~1(对齐 build_rerank_model)。
    pub fn build(
        server_type: &str,
        model: &str,
        url: Option<&str>,
        api_key: Option<&str>,
        extra: Option<&Value>,
    ) -> Result<Self, AppError> {
        let default_url = match server_type {
            "dashscope" => DASHSCOPE_RERANK_URL,
            "ollama" => OLLAMA_RERANK_URL,
            // openai 兼容 rerank 协议与 vLLM /v1/rerank 同构, 复用同一实现
            "vllm" | "openai" => VLLM_RERANK_URL,
            other => {
                return Err(AppError::business(format!(
                    "服务方案 {other} 暂不支持重排序"
                )))
            }
        };
        let (score_min, score_max) = score_range(extra);
        Ok(Self {
            server_type: server_type.to_string(),
            model: model.to_string(),
            url: url
                .map(str::trim)
                .filter(|s| !s.is_empty())
                .unwrap_or(default_url)
                .to_string(),
            api_key: api_key.map(str::to_string),
            score_min,
            score_max,
        })
    }

    /// 按配置范围归一化到 [0,1](范围非法时按 0~1 clamp, 对齐 Rerank.normalize_score)
    pub fn normalize_score(&self, raw: f64) -> f64 {
        let span = self.score_max - self.score_min;
        if span <= 0.0 {
            return raw.clamp(0.0, 1.0);
        }
        ((raw - self.score_min) / span).clamp(0.0, 1.0)
    }

    /// 异步重排序: 返回引擎原始分数条目(含 index/relevance_score 等字段)
    pub async fn arerank(
        &self,
        http: &reqwest::Client,
        query: &str,
        documents: &[String],
        top_n: Option<usize>,
    ) -> Result<Vec<Value>, AppError> {
        let (payload, label, timeout) = match self.server_type.as_str() {
            "dashscope" => (self.dashscope_payload(query, documents, top_n), "Dashscope", 60u64),
            "ollama" => (self.ollama_payload(query, documents, top_n), "Ollama", 120u64),
            _ => (self.vllm_payload(query, documents, top_n), "vLLM", 60u64),
        };
        let mut req = http
            .post(&self.url)
            .json(&payload)
            .timeout(Duration::from_secs(timeout));
        // dashscope 必带 Bearer; vllm 服务端开启鉴权时携带(有 api_key 才带); ollama 不带
        match self.server_type.as_str() {
            "dashscope" => req = req.bearer_auth(self.api_key.as_deref().unwrap_or("")),
            _ => {
                if let Some(key) = self.api_key.as_deref().filter(|k| !k.is_empty()) {
                    req = req.bearer_auth(key);
                }
            }
        }
        let resp = req
            .send()
            .await
            .map_err(|e| AppError::internal(format!("{label} 重排序请求失败: {e}")))?;
        let status = resp.status();
        let body = resp.text().await.unwrap_or_default();
        if status.is_client_error() || status.is_server_error() {
            // 错误文案对齐各 Python 实现(带协议名与状态码)
            return Err(AppError::internal(format!(
                "{label} 重排序请求失败({}): {}",
                status.as_u16(),
                super::truncate_body(&body)
            )));
        }
        let value: Value = serde_json::from_str(&body)
            .map_err(|e| AppError::internal(format!("{label} 重排序响应解析失败: {e}")))?;
        result_to_list(&value, label)
    }

    /// dashscope 载荷: qwen 系 `parameters` 包裹(return_documents=false), bge 系顶层平铺
    fn dashscope_payload(&self, query: &str, documents: &[String], top_n: Option<usize>) -> Value {
        let mut payload = json!({
            "model": self.model,
            "input": {"query": query, "documents": documents},
        });
        if self.model.contains("bge") {
            if let Some(n) = top_n.filter(|n| *n > 0) {
                payload["top_n"] = json!(n);
            }
        } else {
            let mut parameters = json!({"return_documents": false});
            if let Some(n) = top_n.filter(|n| *n > 0) {
                parameters["top_n"] = json!(n);
            }
            payload["parameters"] = parameters;
        }
        payload
    }

    /// ollama 载荷: top_n 顶层传 + parameters 兜底兼容
    fn ollama_payload(&self, query: &str, documents: &[String], top_n: Option<usize>) -> Value {
        let mut payload = json!({
            "model": self.model,
            "query": query,
            "documents": documents,
        });
        if let Some(n) = top_n.filter(|n| *n > 0) {
            payload["top_n"] = json!(n);
            payload["parameters"] = json!({"top_n": n});
        }
        payload
    }

    /// vllm/openai 载荷: jina 兼容协议, top_n 顶层传
    fn vllm_payload(&self, query: &str, documents: &[String], top_n: Option<usize>) -> Value {
        let mut payload = json!({
            "model": self.model,
            "query": query,
            "documents": documents,
        });
        if let Some(n) = top_n.filter(|n| *n > 0) {
            payload["top_n"] = json!(n);
        }
        payload
    }
}

/// 从 extra 读取分数范围(score_min/score_max), 非法回退 0~1(对齐 build_rerank_model._range)
fn score_range(extra: Option<&Value>) -> (f64, f64) {
    let Some(extra) = extra else {
        return (0.0, 1.0);
    };
    let (Some(min), Some(max)) = (
        extra.get("score_min").and_then(Value::as_f64),
        extra.get("score_max").and_then(Value::as_f64),
    ) else {
        return (0.0, 1.0);
    };
    if max <= min {
        tracing::warn!("rerank 分数范围非法(score_max<=score_min): {min}/{max}, 回退 0~1");
        return (0.0, 1.0);
    }
    (min, max)
}

/// 响应 → 结果列表(dashscope: output.results; vllm/ollama: results 或裸列表)
fn result_to_list(value: &Value, label: &str) -> Result<Vec<Value>, AppError> {
    if label == "Dashscope" {
        return value
            .pointer("/output/results")
            .and_then(Value::as_array)
            .cloned()
            .ok_or_else(|| {
                AppError::internal(format!("{label} 重排序响应缺少 output.results"))
            });
    }
    if let Some(list) = value.get("results").and_then(Value::as_array) {
        return Ok(list.clone());
    }
    if let Some(list) = value.as_array() {
        return Ok(list.clone());
    }
    Ok(vec![])
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn 分数范围读取与回退() {
        assert_eq!(score_range(None), (0.0, 1.0));
        assert_eq!(score_range(Some(&json!({"score_min": -0.5, "score_max": 0.5}))), (-0.5, 0.5));
        // 非法范围回退 0~1
        assert_eq!(score_range(Some(&json!({"score_min": 1.0, "score_max": 0.0}))), (0.0, 1.0));
    }

    #[test]
    fn 归一化覆盖负量纲与clamp() {
        let engine = RerankEngine::build("dashscope", "gte-rerank-v2", None, None, None).expect("构建");
        assert!((engine.normalize_score(0.5) - 0.5).abs() < 1e-9);

        let shifted = RerankEngine::build(
            "vllm",
            "jina-reranker-v3",
            None,
            None,
            Some(&json!({"score_min": -0.5, "score_max": 0.5})),
        )
        .expect("构建");
        assert!((shifted.normalize_score(-0.5) - 0.0).abs() < 1e-9);
        assert!((shifted.normalize_score(0.5) - 1.0).abs() < 1e-9);
        // 越界 clamp
        assert_eq!(shifted.normalize_score(2.0), 1.0);
    }

    #[test]
    fn 不支持的方案报业务错误() {
        let err = RerankEngine::build("aws", "x", None, None, None).expect_err("应报错");
        assert!(err.to_string().contains("暂不支持重排序"));
    }
}
