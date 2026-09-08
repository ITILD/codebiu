// src/modules/agent/types/index.ts
// 智能体(agent)模块类型定义
// 会话/消息复用 rag 的 Conversation/ChatMessage 结构(同一套表, agent_id 隔离)

// ---------------- 智能体 ----------------

interface Agent {
  id: string;
  name: string;
  description: string;
  /** 系统提示词(agent 人设与行为规则) */
  system_prompt: string;
  /** 是否公共(所有用户可用) */
  is_public: boolean;
  /** 是否内置种子(启动时幂等写入) */
  is_builtin: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

interface AgentCreate {
  name: string;
  description?: string;
  system_prompt: string;
}

interface AgentUpdate {
  name?: string;
  description?: string;
  system_prompt?: string;
}

// ---------------- 对话(与 rag 的 Conversation 同构) ----------------

interface AgentConversation {
  id: string;
  user_id: string;
  title: string;
  agent_id?: string | null;
  project_ids: string[];
  created_at: string;
  updated_at: string;
}

interface AgentConversationCreate {
  title: string;
  agent_id?: string | null;
}

// 智能体聊天请求(agent 由对话记录决定, 后端自动解析)
interface AgentChatRequest {
  message: string;
}

export type { Agent, AgentCreate, AgentUpdate, AgentConversation, AgentConversationCreate, AgentChatRequest };
