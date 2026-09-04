// src/modules/rag/api/conversation.ts
// 知识库对话 API(对话管理 + RAG 流式聊天)
import { http_base_server } from '@/common/api/http';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import { useAuthStore } from '@/common/stores/auth';
import type { PaginationParams, PaginationResponse } from '@/common/types/common';
import type {
  Conversation,
  ConversationCreate,
  ConversationUpdate,
  ChatMessage,
  RagChatRequest,
  ConversationSummary,
} from '../types';
import type { ChatStreamEvent } from '@/common/types/chat';

/**
 * 创建对话
 * @param data 对话数据(标题/关联知识库)
 * @returns 对话ID
 */
export const createConversation = (data: ConversationCreate) => {
  return http_base_server.post<string>('/rag/conversations', data);
};

/**
 * 获取我的对话列表
 * @param params 分页参数
 */
export const listMyConversations = (params: PaginationParams) => {
  return http_base_server.get<PaginationResponse<Conversation>>(
    '/rag/conversations/my',
    { params }
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
 * RAG 流式聊天(SSE)
 * @param conversationId 对话ID
 * @param request 聊天请求(消息内容/关联知识库/深度思考)
 * @param onChunk 流式内容回调(兼容旧签名, 仅正式回答与过程片段文本)
 * @param onError 错误回调
 * @param onComplete 完成回调
 * @param onController 中止控制器回调(用于页面"停止生成")
 * @param onEvent 完整事件回调(含 node_name/stream_event_type, 供过程区块分组)
 */
export const sendRagChatStream = async (
  conversationId: string,
  request: RagChatRequest,
  onChunk: (content: string) => void,
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
    `/base_server/rag/rag-chat/${conversationId}/chat`,
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
          // 有实际内容时才触发回调
          if (parsed.content && parsed.content.trim()) {
            onChunk(parsed.content);
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
