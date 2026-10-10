// AG-UI 协议(Agent User Interaction Protocol)前端类型定义
// 事件类型/枚举直接 re-export 官方 TS SDK `@ag-ui/core`(由 1.0 规范 schema 生成),
// 与后端官方 Python SDK(ag-ui-protocol)的序列化输出逐字段一致:
// 每条 SSE data 为 camelCase JSON(可选字段缺省时省略), 以大写 type 判别。
// 规范: https://docs.ag-ui.com/concepts/events
//
// 官方包定位:
// - @ag-ui/core  : 协议类型/事件判别联合(Event)与 EventType 枚举, 本文件来源
// - @ag-ui/client: 标准客户端(HttpAgent/MessageQueue), 面向 RunAgentInput 标准
//   端点(threadId/runId/messages/tools/...)。本项目后端为自定义请求体
//   (RagChatRequest/ChatRequest)且需注入鉴权 token, 故传输层用自研
//   aguiStream.ts + useAguiMessages.ts(语义对标官方), 类型层用官方;
//   后端若对齐标准 RunAgentInput 端点, 可切换 HttpAgent 无缝接入
//   CopilotKit 等标准前端。

// ──────────────────────────────────────────────
// 官方协议类型 re-export(@ag-ui/core)
// ──────────────────────────────────────────────

/** 事件类型判别枚举(31 种标准事件, 字符串枚举) */
export { EventType } from '@ag-ui/core'

/** 官方事件判别联合(全量标准事件的 closed union) */
export type { Event as AguiEvent } from '@ag-ui/core'

// 生命周期
export type {
  RunStartedEvent,
  RunFinishedEvent,
  RunErrorEvent,
  StepStartedEvent,
  StepFinishedEvent,
} from '@ag-ui/core'

// 文本消息流
export type {
  TextMessageStartEvent,
  TextMessageContentEvent,
  TextMessageEndEvent,
} from '@ag-ui/core'

// 工具调用流
export type {
  ToolCallStartEvent,
  ToolCallArgsEvent,
  ToolCallEndEvent,
  ToolCallResultEvent,
} from '@ag-ui/core'

// 状态快照
export type { StateSnapshotEvent } from '@ag-ui/core'

// 推理过程流
export type {
  ReasoningStartEvent,
  ReasoningMessageStartEvent,
  ReasoningMessageContentEvent,
  ReasoningMessageEndEvent,
  ReasoningEndEvent,
} from '@ag-ui/core'

// 官方名为 CustomEvent, 重命名避免与 DOM 全局 CustomEvent 类型冲突
export type { CustomEvent as AguiCustomEvent } from '@ag-ui/core'

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
// 用户交互(澄清 / 知识缺口补充) — 本项目业务扩展, 非协议部分
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
// 结构化业务载荷(TOOL_CALL_RESULT content / CUSTOM value)
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
