//! 智能体聊天 DTO(对齐 Python module_agent/do/agent_chat.py)

use serde::Deserialize;

/// 智能体聊天请求(agent 由对话记录的 agent_id 决定, 前端无需传)
#[derive(Debug, Clone, Deserialize)]
pub struct AgentChatRequest {
    pub message: String,
}
