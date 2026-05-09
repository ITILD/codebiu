/**
 * 宝宝名字预测相关的 API 接口
 */
import { http_base_server } from '@/utils/http'
import { fetchEventSource } from '@microsoft/fetch-event-source'
import type {
  NameInfoPredictFullRequest,
  NameInfoResultList,
  NameInfoResult,
} from '@/types/life/baby_name'

/**
 * 推测宝宝五行星座名字（流式 SSE）
 * @param request 预测请求参数
 * @param onChunk 接收数据块的回调函数
 * @param onError 错误回调函数
 * @param onComplete 完成回调函数
 */
export const predictBabyNameStream = async (
  request: NameInfoPredictFullRequest,
  onChunk: (result: NameInfoResult) => void,
  onError?: (error: string) => void,
  onComplete?: () => void,
) => {
  await fetchEventSource(`/base_server/life/baby_name/predict_baby_info_base`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
    onmessage: (event) => {
      try {
        const parsed = JSON.parse(event.data)

        if (parsed.status === 'error') {
          onError?.(parsed.content || '未知错误')
          return
        }

        // 有实际内容时才触发回调 stream
        if (parsed.content && parsed.content.trim()) {
          onChunk(parsed)
        }

        if (parsed.status === 'end') {
          onComplete?.()
        }
      } catch (e) {
        console.warn('解析 SSE 数据失败:', e)
      }
    },
    onerror: (error) => {
      console.error('流式请求失败:', error)
      onError?.(error.message || '请求失败')
      throw error
    },
    onclose: () => {
      onComplete?.()
    },
  })
}
