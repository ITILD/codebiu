// AG-UI 协议(Agent User Interaction Protocol)前端类型定义
// 对齐后端 module_ai/utils/llm/stream/agui.py 输出的官方 SDK 事件流
// (Python 官方包 `ag-ui-protocol`, 每条 data 为 camelCase JSON, 以大写 type 判别)
// 规范参考: https://docs.ag-ui.com/concepts/events
//
// 关于官方 TS SDK:
// 前端官方包为 `@ag-ui/core`(事件/消息类型)与 `@ag-ui/client`(HttpAgent 客户端,
// 自带事件订阅/状态合成/中断恢复)。本文件类型与 @ag-ui/core 1.0 的事件形状
// 逐字段对齐(camelCase, 可选字段可缺省), 当前以零依赖的自实现类型运行;
// 后续如需接入 CopilotKit 等标准客户端, 可 `pnpm add @ag-ui/core @ag-ui/client`
// 后将本文件替换为官方类型 re-export, 下游(aguiStream/useAguiMessages)无需改动。

/** AG-UI 标准事件类型 */
export type AguiEventType =
  | 'RUN_STARTED'
  | 'RUN_FINISHED'
  | 'RUN_ERROR'
  | 'STEP_STARTED'
  | 'STEP_FINISHED'
  | 'TEXT_MESSAGE_START'
  | 'TEXT_MESSAGE_CONTENT'
  | 'TEXT_MESSAGE_END'
  | 'TOOL_CALL_START'
  | 'TOOL_CALL_ARGS'
  | 'TOOL_CALL_END'
  | 'TOOL_CALL_RESULT'
  | 'STATE_SNAPSHOT'
  | 'REASONING_START'
  | 'REASONING_MESSAGE_START'
  | 'REASONING_MESSAGE_CONTENT'
  | 'REASONING_MESSAGE_END'
  | 'REASONING_END'
  | 'CUSTOM'

/** AG-UI 事件公共字段 */
export interface AguiBaseEvent {
  type: AguiEventType
  /** Unix 时间戳(秒) */
  timestamp: number
}

// ──────────────────────────────────────────────
// 生命周期事件
// ──────────────────────────────────────────────

export interface RunStartedEvent extends AguiBaseEvent {
  type: 'RUN_STARTED'
  threadId: string
  runId: string
}

export interface RunFinishedEvent extends AguiBaseEvent {
  type: 'RUN_FINISHED'
  threadId: string
  runId: string
}

export interface RunErrorEvent extends AguiBaseEvent {
  type: 'RUN_ERROR'
  message: string
  code?: string | null
}

export interface StepStartedEvent extends AguiBaseEvent {
  type: 'STEP_STARTED'
  /** 步骤名(后端图节点名, 如 intent_analysis/knowledge_search/chat) */
  stepName: string
}

export interface StepFinishedEvent extends AguiBaseEvent {
  type: 'STEP_FINISHED'
  stepName: string
}

// ──────────────────────────────────────────────
// 文本消息事件(正式回答流)
// ──────────────────────────────────────────────

export interface TextMessageStartEvent extends AguiBaseEvent {
  type: 'TEXT_MESSAGE_START'
  messageId: string
  role: string
}

export interface TextMessageContentEvent extends AguiBaseEvent {
  type: 'TEXT_MESSAGE_CONTENT'
  messageId: string
  delta: string
}

export interface TextMessageEndEvent extends AguiBaseEvent {
  type: 'TEXT_MESSAGE_END'
  messageId: string
}

// ──────────────────────────────────────────────
// 工具调用事件(知识库检索等)
// ──────────────────────────────────────────────

export interface ToolCallStartEvent extends AguiBaseEvent {
  type: 'TOOL_CALL_START'
  toolCallId: string
  toolCallName: string
  /** 调用入参(JSON 字符串) */
  input?: string
}

export interface ToolCallArgsEvent extends AguiBaseEvent {
  type: 'TOOL_CALL_ARGS'
  toolCallId: string
  delta: string
}

export interface ToolCallEndEvent extends AguiBaseEvent {
  type: 'TOOL_CALL_END'
  toolCallId: string
}

export interface ToolCallResultEvent extends AguiBaseEvent {
  type: 'TOOL_CALL_RESULT'
  messageId: string
  toolCallId: string
  role: string
  /** 工具结果(JSON 字符串或文本) */
  content: string
}

// ──────────────────────────────────────────────
// 状态快照事件
// ──────────────────────────────────────────────

export interface StateSnapshotEvent extends AguiBaseEvent {
  type: 'STATE_SNAPSHOT'
  snapshot: Record<string, unknown>
}

// ──────────────────────────────────────────────
// 推理过程事件(思考流)
// ──────────────────────────────────────────────

export interface ReasoningStartEvent extends AguiBaseEvent {
  type: 'REASONING_START'
  id: string
}

export interface ReasoningMessageStartEvent extends AguiBaseEvent {
  type: 'REASONING_MESSAGE_START'
  id: string
}

export interface ReasoningMessageContentEvent extends AguiBaseEvent {
  type: 'REASONING_MESSAGE_CONTENT'
  id: string
  delta: string
}

export interface ReasoningMessageEndEvent extends AguiBaseEvent {
  type: 'REASONING_MESSAGE_END'
  id: string
}

export interface ReasoningEndEvent extends AguiBaseEvent {
  type: 'REASONING_END'
  id: string
}

// ──────────────────────────────────────────────
// 特殊事件(自定义业务载荷)
// ──────────────────────────────────────────────

/** CUSTOM 事件(避免与 DOM 全局 CustomEvent 类型冲突) */
export interface AguiCustomEvent extends AguiBaseEvent {
  type: 'CUSTOM'
  /** 自定义事件名(命名空间.事件) */
  name: string
  value: Record<string, unknown>
}

/** AG-UI 事件联合类型 */
export type AguiEvent =
  | RunStartedEvent
  | RunFinishedEvent
  | RunErrorEvent
  | StepStartedEvent
  | StepFinishedEvent
  | TextMessageStartEvent
  | TextMessageContentEvent
  | TextMessageEndEvent
  | ToolCallStartEvent
  | ToolCallArgsEvent
  | ToolCallEndEvent
  | ToolCallResultEvent
  | StateSnapshotEvent
  | ReasoningStartEvent
  | ReasoningMessageStartEvent
  | ReasoningMessageContentEvent
  | ReasoningMessageEndEvent
  | ReasoningEndEvent
  | AguiCustomEvent

/** CUSTOM 事件名约定(与后端 agui.py 的 CUSTOM_NAME_* 一致) */
export const AGUI_CUSTOM_NAME = {
  /** RAG 进度提示 { message, node } */
  STATUS: 'rag.status',
  /** 意图分析结构化结论 */
  INTENT_RESULT: 'rag.intent_result',
  /** 用户交互请求卡片(InteractionSpec) */
  INTERACTION: 'rag.interaction',
} as const

// ──────────────────────────────────────────────
// 用户交互(澄清 / 知识缺口补充)
// ──────────────────────────────────────────────

/** 交互类型: clarify=信息不足澄清, knowledge_gap=检索零命中补充 */
export type InteractionKind = 'clarify' | 'knowledge_gap'

/** 交互卡片选项 */
export interface InteractionOption {
  label: string
  value: string
  description?: string
}

/** 交互卡片描述(对齐后端 InteractionSpec, snake_case 字段) */
export interface InteractionSpec {
  interaction_id: string
  kind: InteractionKind
  title: string
  question: string
  options: InteractionOption[]
  /** 是否允许文本输入 */
  allow_text: boolean
  text_placeholder?: string
  /** 附加上下文(intent/query/project_ids 等) */
  context?: Record<string, unknown>
}

/** 交互响应动作: submit=提交文本, skip=跳过, supplement=补充内容, answer_directly=直接AI回答, rephrase=换问法重检 */
export type InteractionAction =
  | 'submit'
  | 'skip'
  | 'supplement'
  | 'answer_directly'
  | 'rephrase'

/** 交互响应载荷(回传后端 interaction_response) */
export interface InteractionResponsePayload {
  interaction_id: string
  action: InteractionAction
  value?: string
}

/** 消息内交互卡片快照(渲染 + 已响应状态) */
export interface MessageInteraction {
  spec: InteractionSpec
  /** 是否已响应(已响应后卡片收起为紧凑态) */
  responded: boolean
  /** 用户的响应(已响应时展示) */
  response?: InteractionResponsePayload | null
}

// ──────────────────────────────────────────────
// 结构化业务载荷(TOOL_CALL_RESULT / CUSTOM value)
// ──────────────────────────────────────────────

/** 知识库检索单条结果(引用溯源) */
export interface KnowledgeSearchResult {
  /** 引用来源(文档名) */
  source: string
  score: number
  document_id?: string | null
  chunk_id?: string | null
  project_id?: string | null
  summary?: string
  content?: string
}

/** 知识库检索结构化结果(tool_call 块 data / TOOL_CALL_RESULT content) */
export interface KnowledgeSearchData {
  tool_name?: string
  hit_count?: number
  search_error?: string | null
  request?: Record<string, unknown> | null
  results?: KnowledgeSearchResult[]
}

/** 意图分析结构化结论(CUSTOM rag.intent_result value) */
export interface IntentResultData {
  intent?: string
  vector_search?: string
  is_need_external_info?: boolean
  needs_clarification?: boolean
  clarify_question?: string
  /** 意图分析结论文本 */
  conclusion?: string
}
