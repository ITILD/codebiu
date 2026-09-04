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
  model_id: string
  messages: string | Array<{
    role: 'user' | 'assistant' | 'system'
    content: string
  }>
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

// ==================== 流式聊天事件(对应后端 StreamChunkResponse) ====================

/** 流式事件分类: 区分正式回答与思考/检索等过程区块 */
enum StreamEventType {
  /** LLM 推理过程(reasoning tokens) */
  LLM_THINKING = 'llm_thinking',
  /** 策略思考(意图识别等) */
  AGENT_THINKING = 'agent_thinking',
  /** 思考结论 */
  AGENT_THINKING_CONCLUSION = 'agent_thinking_conclusion',
  /** 工具调用(知识库检索结果/引用溯源) */
  TOOL_CALL = 'tool_call',
  /** 文件生成 */
  FILE_GEN = 'file_gen',
  /** 正式回答 */
  ANSWER = 'answer',
  /** 状态提示(阶段性进度) */
  STATUS = 'status',
  /** 错误 */
  ERROR = 'error',
}

/**
 * 流式聊天单个事件
 * - status: start/stream/end/error(响应状态)
 * - content: 本片段内容
 * - node_name: 后端节点名(intent_analysis/knowledge_search/chat)
 * - stream_event_type: 事件分类(见 StreamEventType)
 */
interface ChatStreamEvent {
  status: string
  content?: string | null
  response_id?: string
  node_name?: string | null
  stream_event_type?: string | null
}

// ==================== 消息内容区块(过程区块/正式回答) ====================

/** 区块渲染类型 */
type MessageBlockType =
  | 'text'           // 普通文本/markdown(正式回答)
  | 'mermaid'        // mermaid 流程图
  | 'process'        // 思考/检索等过程内容(折叠展示)

/** 单个消息内容块(按 stream_event_type 分组) */
interface MessageBlock {
  id: string
  /** 后端节点名 */
  node_name: string
  /** 前端渲染类型 */
  type: MessageBlockType
  /** 块内容(markdown/检索结果) */
  content: string
  /** 后端流式事件分类(answer/llm_thinking/tool_call/status...) */
  stream_event_type?: string
}

/** 带过程区块的聊天消息(助手消息) */
interface ChatMessageWithBlocks extends ChatMessage {
  /** 多区块内容(思考/检索过程 + 正式回答) */
  blocks?: MessageBlock[]
}

/** 消息列表展示用消息(兼容 RAG 会话消息与普通 AI 聊天消息) */
interface DisplayMessage {
  id: string
  /** 消息角色(非 'user' 一律按助手样式渲染) */
  role: string
  content: string
  /** 助手消息的过程区块(思考/检索等, 折叠展示) */
  blocks?: MessageBlock[] | null
  created_at?: string
}

/** 流式事件分类 → 折叠区小标题 */
const STREAM_TYPE_LABELS: Record<string, string> = {
  [StreamEventType.LLM_THINKING]: '推理过程',
  [StreamEventType.AGENT_THINKING]: '意图分析',
  [StreamEventType.AGENT_THINKING_CONCLUSION]: '分析结论',
  [StreamEventType.TOOL_CALL]: '知识检索',
  [StreamEventType.FILE_GEN]: '文件生成',
  [StreamEventType.STATUS]: '进度',
  [StreamEventType.ERROR]: '错误信息',
}

export { StreamEventType, STREAM_TYPE_LABELS }
export type { ChatStreamEvent, MessageBlock, MessageBlockType, ChatMessageWithBlocks, DisplayMessage }
