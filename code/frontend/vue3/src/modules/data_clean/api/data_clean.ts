// src/modules/data_clean/api/data_clean.ts
import { http_base_server } from '@/common/api/http'
import type { DataCleanRequest, DataCleanResponse } from '../types/data_clean'

/**
 * LLM 数据清洗: 对输入数据(JSON 或字符串)按清洗提示词与输出类型进行清洗
 * @param request 数据清洗请求
 * @returns 清洗结果
 */
export const cleanData = (request: DataCleanRequest) => {
  return http_base_server.post<DataCleanResponse>('/data-clean/clean', request)
}
