// src/modules/ai/types/data_clean.ts
// LLM 数据清洗类型定义

/** 输出类型: json=结构化 JSON, string=纯字符串 */
export type DataCleanOutputType = 'json' | 'string'

/** 数据清洗请求 */
export interface DataCleanRequest {
  /** 模型配置ID或模型标识名称 */
  model_id: string
  /** 待清洗数据(JSON 对象/数组或字符串) */
  data: unknown
  /** 清洗提示词(说明清洗规则/目标) */
  prompt: string
  /** 输出类型 */
  output_type: DataCleanOutputType
  /** 输出 JSON 结构(JSON Schema), output_type=json 时建议提供 */
  json_schema?: Record<string, unknown>
}

/** 数据清洗响应 */
export interface DataCleanResponse {
  /** 清洗结果: string 类型为字符串, json 类型为结构化对象 */
  result: unknown
}
