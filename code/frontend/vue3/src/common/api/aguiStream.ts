// AG-UI 协议 SSE 流式请求封装(POST + Bearer token + 事件分发)
// 消费后端 agui_event_generator 输出: 每条 data 为含大写 type 字段的 camelCase JSON
// (后端基于官方 SDK ag-ui-protocol, 序列化 model_dump_json(by_alias=True))
//
// 对标官方 TS 客户端: `@ag-ui/client` 的 HttpAgent(url + headers + run()) 内部
// 同样走 fetch-event-source 并按 RUN_ERROR/RUN_FINISHED 分发事件; 本封装保持
// 项目现有的回调式 API 形态并叠加认证 token 注入, 语义与官方一致。
import { fetchEventSource } from '@microsoft/fetch-event-source'
import { useAuthStore } from '@/common/stores/auth'
import { EventType } from '@/common/types/agui'
import type { AguiEvent } from '@/common/types/agui'

export interface AguiStreamCallbacks {
  /** 每条 AG-UI 事件(含生命周期/文本/推理/工具/自定义事件) */
  onEvent: (event: AguiEvent) => void
  /** RUN_ERROR 事件或传输层错误 */
  onError?: (message: string) => void
  /** RUN_FINISHED 或流正常关闭 */
  onComplete?: () => void
  /** 中止控制器(供页面"停止生成") */
  onController?: (controller: AbortController) => void
}

/** 从认证 store 读取访问令牌(SSE 请求需手动携带; 未登录/未初始化返回空) */
function resolveToken(): string {
  try {
    return useAuthStore().authState.tokens.access.token || ''
  } catch {
    return ''
  }
}

/**
 * 发起 AG-UI 协议流式请求(SSE)
 * @param url 接口地址(如 /base_server/rag/rag-chat/{id}/chat)
 * @param body 请求体(需携带 event_protocol: 'agui')
 * @param callbacks 事件回调组
 * @returns 中止控制器
 */
export async function streamAguiEvents(
  url: string,
  body: unknown,
  callbacks: AguiStreamCallbacks
): Promise<AbortController> {
  const controller = new AbortController()
  callbacks.onController?.(controller)

  const token = resolveToken()
  let errored = false
  let finished = false
  const finish = () => {
    if (!finished) {
      finished = true
      callbacks.onComplete?.()
    }
  }

  try {
    await fetchEventSource(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
      signal: controller.signal,
      onmessage: (event) => {
        try {
          const parsed = JSON.parse(event.data) as AguiEvent
          callbacks.onEvent(parsed)
          if (parsed.type === EventType.RUN_ERROR) {
            errored = true
            callbacks.onError?.(parsed.message || '未知错误')
          } else if (parsed.type === EventType.RUN_FINISHED) {
            finish()
          }
        } catch (e) {
          console.warn('解析AG-UI事件失败:', e)
        }
      },
      onerror: (error) => {
        console.error('AG-UI流式请求失败:', error)
        if (!errored) {
          errored = true
          callbacks.onError?.(error.message || '请求失败')
        }
        // 抛出以停止自动重试(流式接口重试会重复生成)
        throw error
      },
      onclose: () => {
        // RUN_ERROR 结束的流没有 RUN_FINISHED, 不重复触发完成回调
        if (!errored) finish()
      },
    })
  } catch {
    // 传输层错误已通过 onError 通知, 此处吞掉避免调用方重复处理
  }
  return controller
}
