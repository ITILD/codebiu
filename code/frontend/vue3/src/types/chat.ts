// AI聊天相关类型定义

export interface ChatHistory {
  id: string
  title: string
  createdAt: Date
  updatedAt: Date
  messageCount: number
}

export interface ChatMessage {
  id: string
  chatId: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  isStreaming?: boolean
}

export interface ModelConfig {
  id: string
  name: string
  type: 'chat' | 'embedding' | 'rerank'
  description?: string
  isActive?: boolean
}

// API请求/响应类型
export interface ChatRequest {
  modelId: string
  messages: ChatMessage[]
  streaming?: boolean
}

export interface ChatResponse {
  id: string
  content: string
  role: 'assistant'
  timestamp: Date
}

// 流式响应类型
export interface StreamingResponse {
  content: string
  isDone?: boolean
}

// 聊天会话管理
export interface CreateChatRequest {
  title?: string
}

export interface UpdateChatRequest {
  title?: string
}

// 消息格式处理
export interface MessageFormatOptions {
  enableMarkdown?: boolean
  enableCodeHighlight?: boolean
  enableEmoji?: boolean
}

// 聊天状态
export interface ChatState {
  currentChat: ChatHistory | null
  messages: ChatMessage[]
  isLoading: boolean
  isSending: boolean
  error: string | null
}

// 模型配置状态
export interface ModelConfigState {
  availableModels: ModelConfig[]
  selectedModel: string | null
  isLoading: boolean
}

// 本地存储键名
export const STORAGE_KEYS = {
  CHAT_HISTORY: 'ai_chat_history',
  CURRENT_CHAT: 'ai_current_chat',
  SELECTED_MODEL: 'ai_selected_model'
}