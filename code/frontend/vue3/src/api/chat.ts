/**
 * AI聊天相关的API接口
 */
import { http_base_server } from '@/utils/http'
import type { 
  ChatRequest, 
  ChatResponse, 
  ChatHistory, 
  ChatMessage,
  CreateChatRequest,
  UpdateChatRequest 
} from '@/types/chat'

/**
 * 发送聊天消息
 * @param request 聊天请求
 * @returns 聊天响应
 */
export const sendChatMessage = async (request: ChatRequest) => {
  return http_base_server.post<ChatResponse>('/ai/llm_base/chat', request)
}

/**
 * 流式发送聊天消息
 * @param request 聊天请求
 * @returns 流式响应
 */
export const sendChatMessageStream = async (request: ChatRequest) => {
  return http_base_server.post<ReadableStream>('/ai/llm_base/chat', request, {
    headers: {
      'Accept': 'text/event-stream'
    },
    responseType: 'stream'
  })
}

/**
 * 创建新的聊天会话
 * @param request 创建请求
 * @returns 创建的聊天会话ID
 */
export const createChatSession = async (request: CreateChatRequest) => {
  return http_base_server.post<string>('/ai/chat/sessions', request)
}

/**
 * 获取聊天会话列表
 * @returns 聊天会话列表
 */
export const getChatSessions = async () => {
  return http_base_server.get<ChatHistory[]>('/ai/chat/sessions')
}

/**
 * 获取指定聊天会话的详情
 * @param sessionId 会话ID
 * @returns 聊天会话详情
 */
export const getChatSession = async (sessionId: string) => {
  return http_base_server.get<ChatHistory>(`/ai/chat/sessions/${sessionId}`)
}

/**
 * 更新聊天会话
 * @param sessionId 会话ID
 * @param request 更新请求
 */
export const updateChatSession = async (sessionId: string, request: UpdateChatRequest) => {
  return http_base_server.put<void>(`/ai/chat/sessions/${sessionId}`, request)
}

/**
 * 删除聊天会话
 * @param sessionId 会话ID
 */
export const deleteChatSession = async (sessionId: string) => {
  return http_base_server.delete<void>(`/ai/chat/sessions/${sessionId}`)
}

/**
 * 获取聊天会话的消息列表
 * @param sessionId 会话ID
 * @returns 消息列表
 */
export const getChatMessages = async (sessionId: string) => {
  return http_base_server.get<ChatMessage[]>(`/ai/chat/sessions/${sessionId}/messages`)
}

/**
 * 清除模型缓存（测试用）
 * @param modelId 模型ID
 */
export const clearModelCache = async (modelId?: string) => {
  const url = modelId 
    ? `/ai/llm_base/_test_cache_clear/${modelId}`
    : '/ai/llm_base/_test_cache_clear'
  return http_base_server.delete<void>(url)
}

/**
 * 校验模型配置
 * @param modelConfig 模型配置
 * @returns 校验结果
 */
export const checkModelConfig = async (modelConfig: any) => {
  return http_base_server.post<{ message: string }>('/ai/llm_base/check_config', modelConfig)
}

// 本地存储相关的辅助函数
export const LocalStorageHelper = {
  /**
   * 保存聊天历史到本地存储
   */
  saveChatHistory: (history: ChatHistory[]) => {
    try {
      localStorage.setItem('ai_chat_history', JSON.stringify(history))
    } catch (error) {
      console.error('保存聊天历史失败:', error)
    }
  },

  /**
   * 从本地存储加载聊天历史
   */
  loadChatHistory: (): ChatHistory[] => {
    try {
      const stored = localStorage.getItem('ai_chat_history')
      if (stored) {
        const history = JSON.parse(stored)
        // 转换日期字符串为Date对象
        return history.map((item: any) => ({
          ...item,
          createdAt: new Date(item.createdAt),
          updatedAt: new Date(item.updatedAt)
        }))
      }
    } catch (error) {
      console.error('加载聊天历史失败:', error)
    }
    return []
  },

  /**
   * 保存当前选中的聊天会话
   */
  saveCurrentChat: (chat: ChatHistory | null) => {
    try {
      localStorage.setItem('ai_current_chat', JSON.stringify(chat))
    } catch (error) {
      console.error('保存当前聊天失败:', error)
    }
  },

  /**
   * 加载当前选中的聊天会话
   */
  loadCurrentChat: (): ChatHistory | null => {
    try {
      const stored = localStorage.getItem('ai_current_chat')
      if (stored) {
        const chat = JSON.parse(stored)
        if (chat) {
          return {
            ...chat,
            createdAt: new Date(chat.createdAt),
            updatedAt: new Date(chat.updatedAt)
          }
        }
      }
    } catch (error) {
      console.error('加载当前聊天失败:', error)
    }
    return null
  },

  /**
   * 保存选中的模型
   */
  saveSelectedModel: (modelId: string) => {
    try {
      localStorage.setItem('ai_selected_model', modelId)
    } catch (error) {
      console.error('保存选中模型失败:', error)
    }
  },

  /**
   * 加载选中的模型
   */
  loadSelectedModel: (): string => {
    try {
      return localStorage.getItem('ai_selected_model') || ''
    } catch (error) {
      console.error('加载选中模型失败:', error)
      return ''
    }
  }
}