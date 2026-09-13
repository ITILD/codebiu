// src/modules/agent/types/index.ts
// 智能体(agent)模块类型定义
// 会话/消息复用 rag 的 Conversation/ChatMessage 结构(同一套表, agent_id 隔离)

// ---------------- 智能体 ----------------

/** 输入/输出类型: str=字符串(默认), json=JSON 结构体 */
type AgentIOType = 'str' | 'json'

/** 智能体类型: simple=简单(默认), workflow=工作流(Vue Flow 图编排) */
type AgentType = 'simple' | 'workflow'

/** 工作流节点类型(第一期 5 类) */
type WorkflowNodeType = 'start' | 'end' | 'llm' | 'condition' | 'template'

/** 工作流节点(Vue Flow node 子集 + 业务 data) */
interface WorkflowNode {
  id: string;
  type: WorkflowNodeType;
  position: { x: number; y: number };
  data: {
    /** LLM 节点: 提示词模板(可含 {{node_id.path}} 引用) */
    prompt?: string;
    /** LLM 节点: 模型配置ID(空则回退运行请求的 model_id) */
    model_id?: string | null;
    /** LLM 节点: 输出类型 */
    output_type?: AgentIOType;
    /** LLM 节点: 输出结构(JSON Schema) */
    output_schema?: Record<string, unknown> | null;
    /** 条件节点: 左值来源节点ID */
    left_source?: string;
    /** 条件节点: 左值字段路径 */
    left_path?: string;
    /** 条件节点: 运算符 */
    operator?: 'eq' | 'ne' | 'gt' | 'gte' | 'lt' | 'lte' | 'contains' | 'empty' | 'regex';
    /** 条件节点: 右值(字面量) */
    right?: string;
    /** 模板节点: 模板文本 */
    template?: string;
    /** 结束节点: 结果模板(空则取最后 LLM 节点输出) */
    result?: string;
  };
}

/** 工作流连线(condition 出边 sourceHandle=true/false 区分分支) */
interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string | null;
}

/** 工作流图(Vue Flow 可视化编辑器的持久化结构) */
interface WorkflowGraph {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  viewport?: { x: number; y: number; zoom: number };
}

/** 工作流节点执行轨迹 */
interface NodeTrace {
  node_id: string;
  node_type: string;
  status: 'success' | 'failed' | 'skipped';
  input?: unknown;
  output?: unknown;
  duration_ms: number;
  error?: string | null;
}

interface Agent {
  id: string;
  name: string;
  description: string;
  /** 系统提示词(agent 人设与行为规则) */
  system_prompt: string;
  /** 智能体类型(默认 simple) */
  agent_type: AgentType;
  /** 工作流图(Vue Flow nodes/edges), agent_type=workflow 时使用 */
  workflow: WorkflowGraph | null;
  /** 输入类型(默认 str) */
  input_type: AgentIOType;
  /** 输出类型(默认 str) */
  output_type: AgentIOType;
  /** 输入结构(JSON Schema), input_type=json 时可选 */
  input_schema: Record<string, unknown> | null;
  /** 输出结构(JSON Schema), output_type=json 时可选(结构化输出约束) */
  output_schema: Record<string, unknown> | null;
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
  agent_type?: AgentType;
  input_type?: AgentIOType;
  output_type?: AgentIOType;
  input_schema?: Record<string, unknown> | null;
  output_schema?: Record<string, unknown> | null;
}

interface AgentUpdate {
  name?: string;
  description?: string;
  system_prompt?: string;
  agent_type?: AgentType;
  workflow?: WorkflowGraph | null;
  input_type?: AgentIOType;
  output_type?: AgentIOType;
  input_schema?: Record<string, unknown> | null;
  output_schema?: Record<string, unknown> | null;
}

/** 保存工作流配置请求(切换类型 + 保存图, 后端先校验) */
interface AgentWorkflowSaveRequest {
  agent_type: AgentType;
  workflow: WorkflowGraph | null;
}

// ---------------- 运行(结构体配置驱动的单次执行) ----------------

interface AgentRunRequest {
  /** 模型配置ID(复用 AI 模块模型配置) */
  model_id: string;
  /** 运行输入: input_type=str 时为字符串, json 时为 JSON 对象/数组 */
  input: unknown;
}

interface AgentRunResponse {
  /** 本次运行记录ID(运行历史可回看) */
  run_id: string;
  /** 运行结果: output_type=str 时为字符串, json 时为结构化对象 */
  result: unknown;
  /** 工作流节点执行轨迹(仅工作流智能体返回) */
  trace?: NodeTrace[] | null;
}

/** 运行历史条目 */
interface AgentRunRecord {
  id: string;
  agent_id: string;
  model_id: string;
  input: unknown;
  output: unknown;
  /** 工作流节点执行轨迹(仅工作流智能体) */
  trace?: { nodes: NodeTrace[] } | null;
  created_at: string;
}

export type {
  AgentIOType, AgentType, Agent, AgentCreate, AgentUpdate, AgentWorkflowSaveRequest,
  WorkflowNodeType, WorkflowNode, WorkflowEdge, WorkflowGraph, NodeTrace,
  AgentRunRequest, AgentRunResponse, AgentRunRecord,
  AgentConversation, AgentConversationCreate, AgentChatRequest,
};

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
