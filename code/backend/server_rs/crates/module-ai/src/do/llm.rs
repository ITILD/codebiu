//! LLM 调用 DTO(对齐 Python module_ai/do/llm.py)

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value;

use common::utils::error::AppError;

/// 消息模型(与 Python do/llm.py Message 兼容; role 兼容 langchain 的 human/ai 别名)
#[derive(Debug, Clone, Deserialize)]
pub struct Message {
    #[serde(default = "d_user_role")]
    pub role: String,
    pub content: String,
    #[serde(default)]
    pub additional_kwargs: Value,
}

fn d_user_role() -> String {
    "user".to_string()
}

impl Message {
    /// 归一化角色: human→user / ai→assistant; 未知角色构造 422(对齐 RoleType 枚举约束)
    pub fn normalized_role(&self) -> Result<String, AppError> {
        let role = match self.role.as_str() {
            "user" | "human" => "user",
            "assistant" | "ai" => "assistant",
            "system" => "system",
            other => {
                return Err(AppError::validation(
                    &["body", "messages", "role"],
                    format!("Input should be 'system', 'user' or 'assistant', got '{other}'"),
                ))
            }
        };
        Ok(role.to_string())
    }
}

/// messages 字段载体: 字符串 → 单条用户消息; 列表 → 消息列表(对齐 ChatRequest 校验器)
#[derive(Debug, Clone, Deserialize)]
#[serde(untagged)]
pub enum MessageInput {
    Text(String),
    List(Vec<Message>),
}

impl MessageInput {
    /// 标准化为消息列表(空列表原样返回, 交由调用方报错)
    pub fn to_messages(&self) -> Result<Vec<Message>, AppError> {
        match self {
            MessageInput::Text(s) => Ok(vec![Message {
                role: "user".to_string(),
                content: s.clone(),
                additional_kwargs: Value::Null,
            }]),
            MessageInput::List(items) => Ok(items.clone()),
        }
    }
}

/// 聊天请求体
#[derive(Debug, Clone, Deserialize)]
pub struct ChatRequest {
    pub model_id: String,
    pub messages: MessageInput,
    #[serde(default)]
    pub streaming: bool,
}

/// 嵌入请求体(预留契约, Python 同名)
#[derive(Debug, Clone, Deserialize)]
pub struct EmbeddingRequest {
    pub model_id: String,
    pub texts: Vec<String>,
}

/// 校验模型格式化能力的结构(对齐 ModelChatCheckFormat)
#[derive(Debug, Clone, Deserialize)]
pub struct ModelChatCheckFormat {
    pub name: String,
    pub age: i64,
}

/// 配置校验响应
#[derive(Debug, Clone, Default, Serialize)]
pub struct ModelConfigCheckResponse {
    #[serde(default)]
    pub is_valid: bool,
    #[serde(default)]
    pub is_format: bool,
}

/// 单项能力测试结果
#[derive(Debug, Clone, Serialize)]
pub struct ModelCapabilityTestItem {
    pub capability: String,
    #[serde(default)]
    pub label: String,
    pub ok: bool,
    #[serde(default)]
    pub detail: String,
    #[serde(default)]
    pub error: String,
    pub elapsed: f64,
    /// 附加建议(rerank: 检测到的分数范围与建议配置)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub suggest: Option<Value>,
}

/// 模型能力测试请求体
#[derive(Debug, Clone, Deserialize)]
pub struct ModelTestRequest {
    pub model_id: String,
    #[serde(default)]
    pub capability: Option<String>,
}

/// 模型能力测试响应(结果已持久化到 model_config.check_result)
#[derive(Debug, Clone, Serialize)]
pub struct ModelTestResponse {
    pub model_id: String,
    pub model_type: String,
    pub capabilities: Vec<ModelCapabilityTestItem>,
    pub checked_at: Option<DateTime<Utc>>,
}

/// 各模型类型支持的能力测试项(对齐 do/llm.py MODEL_CAPABILITIES)
pub fn capabilities_for(type_key: &str) -> Vec<(&'static str, &'static str)> {
    match type_key {
        "chat" => vec![("chat", "问答"), ("structured", "结构化"), ("vision", "多模态")],
        "embeddings" => vec![("embedding", "向量化")],
        "rerank" => vec![("rerank", "重排")],
        "asr" => vec![("asr", "识别")],
        "tts" => vec![("tts", "合成")],
        "vad" => vec![("vad", "断句")],
        "denoise" => vec![("denoise", "降噪")],
        _ => vec![],
    }
}
