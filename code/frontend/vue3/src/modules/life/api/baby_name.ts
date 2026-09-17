/**
 * 宝宝名字预测相关的 API 接口
 */
import { http_base_server } from '@/common/api/http'
import { fetchEventSource } from '@microsoft/fetch-event-source'
import type {
  NameInfoPredictFullRequest,
  NameInfoResultList,
  NameInfoResult,
  FolkReferenceItem,
  ReferenceCalculateRequest,
  ReferenceCalculateResult,
  BabyNameGenerateRequest,
} from '../types/baby_name'

/**
 * 获取起名参考体系目录(五行八字/三才五格/星座/生肖/塔罗/基督/佛教/道教)
 * @return 参考体系目录列表(strict 标记该项是否有经典程序化计算)
 */
export const getReferenceCatalog = async (): Promise<FolkReferenceItem[]> => {
  return await http_base_server.get<FolkReferenceItem[]>('/life/baby-names/references')
}

/**
 * 推算选中参考体系的严格信息(五行八字/星座/生肖/塔罗/姓氏五格基准)
 * @param request 宝宝天生信息与参考体系列表
 * @return 各参考体系推算结果(未选为 null)
 */
export const calculateReference = async (
  request: ReferenceCalculateRequest,
): Promise<ReferenceCalculateResult> => {
  return await http_base_server.post<ReferenceCalculateResult>(
    '/life/baby-names/calculate-reference',
    request,
  )
}

/**
 * 按参考配置流式起名(SSE)
 * 事件节点: calc_*(严格计算结果 markdown) → generate_name_result(名字 markdown)
 * → names_evaluated(程序评定名字清单 JSON)
 * @param request 宝宝信息+参考配置+数量+排除名单
 * @param onChunk 接收节点数据块回调(node_name 区分节点, content 为增量内容, eventType 区分正文/思考)
 * @param onError 错误回调函数
 * @param onComplete 完成回调函数
 */
export const generateBabyNamesStream = async (
  request: BabyNameGenerateRequest,
  onChunk: (nodeName: string, content: string, eventType?: string | null) => void,
  onError?: (error: string) => void,
  onComplete?: () => void,
) => {
  await fetchEventSource(`/base_server/life/baby-names/generate`, {
    method: 'POST',
    // 页面隐藏(切窗口/切标签/最小化)时不中断流, 避免起名中途被 abort
    openWhenHidden: true,
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

        // 有内容即回调(含纯空白块: 空行/缩进是格式的一部分, trim 会丢换行)
        if (parsed.content && parsed.node_name) {
          onChunk(parsed.node_name, parsed.content, parsed.stream_event_type)
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
  await fetchEventSource(`/base_server/life/baby-names/predict-baby-info-base`, {
    method: 'POST',
    // 页面隐藏时不中断流(与 generate 保持一致)
    openWhenHidden: true,
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

        // 有内容即回调(含纯空白块: 空行/缩进是格式的一部分, trim 会丢换行)
        if (parsed.content) {
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
