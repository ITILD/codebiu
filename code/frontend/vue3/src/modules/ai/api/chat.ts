/**
 * AI聊天相关的API接口
 */
import { http_base_server } from '@/common/api/http'
import { fetchEventSource } from '@microsoft/fetch-event-source'
import type {
  ChatRequest,
  ChatResponse,
  ChatHistory,
  ChatStreamEvent
} from '@/common/types/chat'

/**
 * 发送聊天消息
 * @param request 聊天请求
 * @returns 聊天响应
 */
export const sendChatMessage = async (request: ChatRequest) => {
  return http_base_server.post<ChatResponse>('/ai/llm-base/chat', request)
}

/**
 * 流式发送聊天消息 (SSE) - 优化版
 * @param request 聊天请求
 * @param onChunk 接收数据块的回调函数
 * @param onError 错误回调函数
 * @param onComplete 完成回调函数
 * @param onController 中止控制器回调(用于页面"停止生成")
 * @param onEvent 完整事件回调(含 node_name/stream_event_type, 供过程区块分组)
 */
export const sendChatMessageStream = async (
  request: ChatRequest,
  onChunk: (content: string) => void,
  onError?: (error: string) => void,
  onComplete?: () => void,
  onController?: (controller: AbortController) => void,
  onEvent?: (event: ChatStreamEvent) => void
) => {
  const controller = new AbortController()
  // 立即交给调用方, 供流式期间中止
  onController?.(controller)
  await fetchEventSource(`/base_server/ai/llm-base/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(request),
    signal: controller.signal,
    onmessage: (event) => {
      try {
        const parsed = JSON.parse(event.data) as ChatStreamEvent

        if (parsed.status === 'error') {
          onError?.(parsed.content || '未知错误')
          return
        }

        // 有实际内容时才触发回调
        if (parsed.content && parsed.content.trim()) {
          onChunk(parsed.content)
        }

        // 透传完整事件(供页面按事件类型分组过程区块)
        onEvent?.(parsed)

        if (parsed.status === 'end') {
          onComplete?.()
        }
      } catch (e) {
        console.warn('解析SSE数据失败:', e)
      }
    },
    onerror: (error) => {
      console.error('流式请求失败:', error)
      onError?.(error.message || '请求失败')
      throw error
    },
    onclose: () => {
      onComplete?.()
    }
  })
  return controller
}

/**
 * 清除模型缓存（测试用）
 * @param model_id 模型ID(为空清除全部)
 */
export const clearModelCache = async (model_id?: string) => {
  const url = model_id ? `/ai/llm-base/cache/${model_id}` : '/ai/llm-base/cache'
  return http_base_server.delete<void>(url)
}

/**
 * 校验模型配置
 * @param modelConfig 模型配置
 * @returns 校验结果
 */
export const checkModelConfig = async (modelConfig: any) => {
  return http_base_server.post<{ message: string }>('/ai/llm-base/check-config', modelConfig)
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
  saveSelectedModel: (model_id: string) => {
    try {
      localStorage.setItem('ai_selected_model', model_id)
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
