// src/modules/agent/api/agent.ts
// 智能体 API(管理 CRUD + 会话列表 + 流式聊天)
import { http_base_server } from '@/common/api/http';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import { useAuthStore } from '@/common/stores/auth';
import type { PaginationParams, PaginationResponse } from '@/common/types/common';
import type { ChatStreamEvent } from '@/common/types/chat';
import type { ChatMessage } from '../../rag/types';
import type {
  Agent,
  AgentCreate,
  AgentUpdate,
  AgentWorkflowSaveRequest,
  AgentConversation,
  AgentConversationCreate,
  AgentChatRequest,
  AgentRunRequest,
  AgentRunResponse,
  AgentRunRecord,
} from '../types';

// ==================== 智能体管理 ====================

/**
 * 获取可访问的智能体列表(内置公共 + 本人创建)
 * @param params 分页参数
 */
export const listAgents = (params: PaginationParams) => {
  return http_base_server.get<PaginationResponse<Agent>>('/agent/agents', { params });
};

/**
 * 获取智能体详情
 * @param agentId 智能体ID
 */
export const getAgent = (agentId: string) => {
  return http_base_server.get<Agent>(`/agent/agents/${agentId}`);
};

/**
 * 创建自定义简单智能体
 * @param data 智能体数据(名称/描述/系统提示词)
 * @returns 智能体ID
 */
export const createAgent = (data: AgentCreate) => {
  return http_base_server.post<string>('/agent/agents', data);
};

/**
 * 更新智能体(仅创建者或管理员)
 * @param agentId 智能体ID
 * @param data 更新数据
 */
export const updateAgent = (agentId: string, data: AgentUpdate) => {
  return http_base_server.put<void>(`/agent/agents/${agentId}`, data);
};

/**
 * 删除智能体(仅创建者或管理员, 内置不可删)
 * @param agentId 智能体ID
 */
export const deleteAgent = (agentId: string) => {
  return http_base_server.delete<void>(`/agent/agents/${agentId}`);
};

// ==================== 智能体运行(结构体配置驱动) ====================

/**
 * 运行智能体(按结构体配置执行一次输入→输出, 仅公共或本人创建的智能体)
 * @param agentId 智能体ID
 * @param data 运行请求(模型配置ID + 输入数据)
 */
export const runAgent = (agentId: string, data: AgentRunRequest) => {
  return http_base_server.post<AgentRunResponse>(`/agent/agents/${agentId}/run`, data);
};

/**
 * 获取智能体运行历史(仅本人记录, 按时间倒序)
 * @param agentId 智能体ID
 * @param params 分页参数
 */
export const listAgentRuns = (agentId: string, params: PaginationParams) => {
  return http_base_server.get<PaginationResponse<AgentRunRecord>>(
    `/agent/agents/${agentId}/runs`,
    { params }
  );
};

/**
 * 获取单条运行详情(含工作流节点轨迹, 仅本人)
 * @param agentId 智能体ID
 * @param runId 运行记录ID
 */
export const getAgentRunDetail = (agentId: string, runId: string) => {
  return http_base_server.get<AgentRunRecord>(`/agent/agents/${agentId}/runs/${runId}`);
};

// ==================== 工作流配置 ====================

/**
 * 保存工作流配置(切换智能体类型 + 保存图; 后端先静态校验, 失败返回 400)
 * @param agentId 智能体ID
 * @param data 类型与工作流图
 */
export const saveAgentWorkflow = (agentId: string, data: AgentWorkflowSaveRequest) => {
  return http_base_server.put<void>(`/agent/agents/${agentId}/workflow`, data);
};

// ==================== 智能体对话 ====================

/**
 * 创建智能体对话(复用 /rag/conversations, 携带 agent_id)
 * @param data 对话数据(标题/智能体ID)
 * @returns 对话ID
 */
export const createAgentConversation = (data: AgentConversationCreate) => {
  return http_base_server.post<string>('/rag/conversations', data);
};

/**
 * 获取我的智能体对话列表(仅 agent 会话, 可按智能体过滤)
 * @param params 分页参数
 * @param agentId 可选, 按智能体过滤
 */
export const listMyAgentConversations = (params: PaginationParams, agentId?: string) => {
  return http_base_server.get<PaginationResponse<AgentConversation>>(
    '/agent/conversations/my',
    { params: { ...params, agent_id: agentId || undefined } }
  );
};

/**
 * 获取对话详情(复用 /rag/conversations)
 * @param conversationId 对话ID
 */
export const getAgentConversation = (conversationId: string) => {
  return http_base_server.get<AgentConversation>(`/rag/conversations/${conversationId}`);
};

/**
 * 删除对话(复用 /rag/conversations, 同时删除关联消息)
 * @param conversationId 对话ID
 */
export const deleteAgentConversation = (conversationId: string) => {
  return http_base_server.delete<void>(`/rag/conversations/${conversationId}`);
};

/**
 * 获取对话消息列表(复用 /rag/conversations)
 * @param conversationId 对话ID
 * @param params 分页参数
 */
export const listAgentConversationMessages = (
  conversationId: string,
  params: PaginationParams
) => {
  return http_base_server.get<PaginationResponse<ChatMessage>>(
    `/rag/conversations/${conversationId}/messages`,
    { params }
  );
};

/**
 * 智能体流式聊天(SSE)
 * @param conversationId 对话ID
 * @param request 聊天请求(消息内容)
 * @param onError 错误回调
 * @param onComplete 完成回调
 * @param onController 中止控制器回调(用于页面"停止生成")
 * @param onEvent 完整事件回调(含 node_name/stream_event_type, 供过程区块分组)
 */
export const sendAgentChatStream = async (
  conversationId: string,
  request: AgentChatRequest,
  onError?: (error: string) => void,
  onComplete?: () => void,
  onController?: (controller: AbortController) => void,
  onEvent?: (event: ChatStreamEvent) => void
) => {
  // 从认证 store 读取访问令牌(SSE 请求需手动携带)
  let token = '';
  try {
    const authStore = useAuthStore();
    token = authStore.authState.tokens.access.token || '';
  } catch {
    // Pinia 未初始化时忽略
  }

  const controller = new AbortController();
  // 立即交给调用方, 供流式期间中止
  onController?.(controller);
  await fetchEventSource(
    `/base_server/agent/agent-chat/${conversationId}/chat`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(request),
      signal: controller.signal,
      onmessage: (event) => {
        try {
          const parsed = JSON.parse(event.data) as ChatStreamEvent;
          if (parsed.status === 'error') {
            onError?.(parsed.content || '未知错误');
            return;
          }
          // 透传完整事件(供页面按事件类型分组过程区块)
          onEvent?.(parsed);
          if (parsed.status === 'end') {
            onComplete?.();
          }
        } catch (e) {
          console.warn('解析SSE数据失败:', e);
        }
      },
      onerror: (error) => {
        console.error('流式请求失败:', error);
        onError?.(error.message || '请求失败');
        throw error;
      },
      onclose: () => {
        onComplete?.();
      },
    }
  );
  return controller;
};
