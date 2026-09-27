//! 重排序 DTO(对齐 Python module_ai/do/rerank.py)

use serde::{Deserialize, Serialize};
use serde_json::Value;

/// 重排序请求体
#[derive(Debug, Clone, Deserialize)]
pub struct RerankRequest {
    pub query: String,
    /// 待排序文档列表(字符串 或 含 sort_key 字段的字典)
    pub documents: Vec<Value>,
    #[serde(default)]
    pub model_id: Option<String>,
    #[serde(default)]
    pub top_n: Option<i64>,
    #[serde(default = "d_content")]
    pub sort_key: String,
}

fn d_content() -> String {
    "content".to_string()
}

/// 重排序响应(按相关性降序)
#[derive(Debug, Clone, Default, Serialize)]
pub struct RerankResponse {
    /// [{node: 原文档, relevance_score: 相关性分数}]
    pub results: Vec<Value>,
    pub elapsed: f64,
}
