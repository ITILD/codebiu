//! 对话/消息/问答 DTO(对齐 Python module_rag/do/conversation.py、
//! chat_message.py、rag_chat.py), 含流式事件类型常量。

use sea_orm::prelude::{DateTimeWithTimeZone, Json};
use serde::{Deserialize, Serialize};

use crate::do_::entity::{chat_message, conversation};

// ==================== 对话 ====================

/// 创建对话请求
#[derive(Debug, Deserialize)]
pub struct ConversationCreate {
    pub title: String,
    #[serde(default)]
    pub agent_id: Option<String>,
    #[serde(default)]
    pub project_ids: Vec<String>,
}

/// 更新对话请求(None=不更新)
#[derive(Debug, Default, Deserialize)]
pub struct ConversationUpdate {
    #[serde(default)]
    pub title: Option<String>,
    #[serde(default)]
    pub agent_id: Option<String>,
    #[serde(default)]
    pub project_ids: Option<Vec<String>>,
}

/// 对话响应
#[derive(Debug, Serialize)]
pub struct ConversationResponse {
    pub id: String,
    pub user_id: String,
    pub title: String,
    pub agent_id: Option<String>,
    pub project_ids: Vec<String>,
    pub created_at: Option<DateTimeWithTimeZone>,
    pub updated_at: DateTimeWithTimeZone,
}

impl From<conversation::Model> for ConversationResponse {
    fn from(m: conversation::Model) -> Self {
        Self {
            id: m.id,
            user_id: m.user_id,
            title: m.title,
            agent_id: m.agent_id,
            project_ids: json_to_string_vec(&m.project_ids),
            created_at: m.created_at,
            updated_at: m.updated_at,
        }
    }
}

/// JSON 列(project_ids) → 字符串数组(空值归一化为空数组)
pub fn json_to_string_vec(v: &Json) -> Vec<String> {
    match v {
        serde_json::Value::Array(items) => items
            .iter()
            .filter_map(|i| i.as_str().map(str::to_string))
            .collect(),
        _ => Vec::new(),
    }
}

/// 字符串数组 → JSON 列(project_ids)
pub fn string_vec_to_json(ids: &[String]) -> Json {
    serde_json::Value::Array(ids.iter().map(|s| serde_json::Value::String(s.clone())).collect())
        .into()
}

// ==================== 聊天消息 ====================

/// 聊天消息响应
#[derive(Debug, Serialize)]
pub struct ChatMessageResponse {
    pub id: String,
    pub conversation_id: String,
    /// 消息角色(user/assistant/system, 小写对齐 Python RoleType)
    pub role: String,
    pub content: String,
    pub created_at: Option<DateTimeWithTimeZone>,
    pub blocks: Option<Json>,
}

impl From<chat_message::Model> for ChatMessageResponse {
    fn from(m: chat_message::Model) -> Self {
        Self {
            id: m.id,
            conversation_id: m.conversation_id,
            role: m.role.as_str().to_string(),
            content: m.content,
            created_at: m.created_at,
            blocks: m.blocks,
        }
    }
}

// ==================== 知识库问答(rag_chat) ====================

/// 发起问答请求
#[derive(Debug, Deserialize)]
pub struct ChatRequest {
    pub message: String,
    #[serde(default)]
    pub project_ids: Vec<String>,
    #[serde(default)]
    pub deep_thinking: bool,
    #[serde(default = "d_rerank_limit")]
    pub rerank_limit: i64,
}

fn d_rerank_limit() -> i64 {
    20
}

/// 对话总结响应(summarize 端点; 失败/无模型时返回默认值)
#[derive(Debug, Serialize)]
pub struct ConversationSummary {
    pub title: String,
    pub summary: String,
}

impl Default for ConversationSummary {
    fn default() -> Self {
        Self { title: String::new(), summary: String::new() }
    }
}

// ==================== 流式事件类型(对齐 StreamEventType StrEnum) ====================

/// 流式输出事件分类值(SSE 事件 stream_event_type 字段)
pub mod stream_event_type {
    /// LLM 推理/思考过程
    pub const LLM_THINKING: &str = "llm_thinking";
    /// 策略思考过程(意图识别等)
    pub const AGENT_THINKING: &str = "agent_thinking";
    /// 思考结论
    pub const AGENT_THINKING_CONCLUSION: &str = "agent_thinking_conclusion";
    /// 工具调用(知识库检索等)
    pub const TOOL_CALL: &str = "tool_call";
    /// 文件生成
    pub const FILE_GEN: &str = "file_gen";
    /// 正式回答
    pub const ANSWER: &str = "answer";
    /// 状态更新(进度提示)
    pub const STATUS: &str = "status";
    /// 错误信息
    pub const ERROR: &str = "error";
}

/// RAG 图节点名(对齐 GraphNode StrEnum)
pub mod graph_node {
    pub const INTENT: &str = "intent_analysis";
    pub const SEARCH: &str = "knowledge_search";
    pub const CHAT: &str = "chat";
    pub const SUMMARY: &str = "summarize";
}

/// 节点名 → 前端状态提示(对齐 NODE_STATUS_MAP)
pub fn node_status(node: &str) -> &'static str {
    match node {
        graph_node::INTENT => "正在分析意图…",
        graph_node::SEARCH => "正在检索知识库…",
        graph_node::CHAT => "正在生成回答…",
        _ => "",
    }
}

/// 过程区块(落库 chat_message.blocks, 前端折叠区恢复显示)
#[derive(Debug, Clone, Serialize)]
pub struct ProcessBlock {
    /// 区块类型(对齐 StreamEventType 值)
    pub event_type: String,
    /// 节点名
    pub node_name: String,
    /// 累积的区块内容
    pub content: String,
}
