// src/modules/rag/api/conversation.ts
// 知识库对话 API(对话管理 + RAG 流式聊天)
// 流式聊天统一走 AG-UI 协议(官方 ag-ui-protocol 事件流, 见 @/common/api/aguiStream)
import { http_base_server } from '@/common/api/http';
import { streamAguiEvents } from '@/common/api/aguiStream';
import type { AguiStreamCallbacks } from '@/common/api/aguiStream';
import type { PaginationParams, PaginationResponse } from '@/common/types/common';
import type {
  Conversation,
  ConversationCreate,
  ConversationUpdate,
  ChatMessage,
  RagChatRequest,
  ConversationSummary,
} from '../types';

/**
 * 创建对话
 * @param data 对话数据(标题/关联知识库)
 * @returns 对话ID
 */
export const createConversation = (data: ConversationCreate) => {
  return http_base_server.post<string>('/rag/conversations', data);
};

/**
 * 获取我的对话列表(知识库问答页使用, 排除智能体对话)
 * @param params 分页参数
 */
export const listMyConversations = (params: PaginationParams) => {
  return http_base_server.get<PaginationResponse<Conversation>>(
    '/rag/conversations/my',
    { params: { ...params, scope: 'rag' } }
  );
};

/**
 * 获取对话详情
 * @param conversationId 对话ID
 */
export const getConversation = (conversationId: string) => {
  return http_base_server.get<Conversation>(
    `/rag/conversations/${conversationId}`
  );
};

/**
 * 更新对话(标题/关联知识库)
 * @param conversationId 对话ID
 * @param data 更新数据
 */
export const updateConversation = (
  conversationId: string,
  data: ConversationUpdate
) => {
  return http_base_server.put<void>(
    `/rag/conversations/${conversationId}`,
    data
  );
};

/**
 * 删除对话(同时删除关联消息)
 * @param conversationId 对话ID
 */
export const deleteConversation = (conversationId: string) => {
  return http_base_server.delete<void>(`/rag/conversations/${conversationId}`);
};

/**
 * 获取对话消息列表
 * @param conversationId 对话ID
 * @param params 分页参数
 */
export const listConversationMessages = (
  conversationId: string,
  params: PaginationParams
) => {
  return http_base_server.get<PaginationResponse<ChatMessage>>(
    `/rag/conversations/${conversationId}/messages`,
    { params }
  );
};

/**
 * 总结历史对话并生成标题
 * @param conversationId 对话ID
 */
export const summarizeConversation = (conversationId: string) => {
  return http_base_server.post<ConversationSummary>(
    `/rag/rag-chat/${conversationId}/summarize`
  );
};

/**
 * RAG 流式聊天(AG-UI 协议 SSE)
 * 事件为 AG-UI 标准事件流(RUN_STARTED / TEXT_MESSAGE / TOOL_CALL / CUSTOM 等),
 * 由 useAguiMessages 聚合为消息内容; 交互卡片响应通过 interaction_response 续跑流程
 * @param conversationId 对话ID
 * @param request 聊天请求
 * @param callbacks 事件回调组
 * @returns 中止控制器
 */
export const sendRagChatAguiStream = async (
  conversationId: string,
  request: RagChatRequest,
  callbacks: AguiStreamCallbacks
) => {
  return streamAguiEvents(
    `/base_server/rag/rag-chat/${conversationId}/chat`,
    request,
    callbacks
  );
};
