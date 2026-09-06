// src/modules/site/api/ledger.ts —— 记账接口(/site/ledger/records)
import { http_base_server } from '@/common/api/http'
import type { PaginationParams, PaginationResponse } from '@/common/types/common'
import type {
  LedgerRecord,
  LedgerRecordCreate,
  LedgerRecordUpdate,
  LedgerStats,
} from '../types/ledger'

/** 记账列表查询参数(分页 + 过滤) */
// 用 type 交叉而非 interface: 接口缺隐式索引签名, 无法赋给 http 层 Record<string, QueryParamValue>
export type ListLedgerParams = PaginationParams & {
  /** 按月过滤 YYYY-MM */
  month?: string
  /** 收支方向过滤(income/expense) */
  flow_type?: string
  /** 分类模糊搜索 */
  category?: string
}

/** 记一笔(收入/支出) */
export const createLedgerRecord = (record: LedgerRecordCreate) => {
  return http_base_server.post<string>('/site/ledger/records', record)
}

/** 删除记账记录(仅本人) */
export const deleteLedgerRecord = (recordId: string) => {
  return http_base_server.delete<void>(`/site/ledger/records/${recordId}`)
}

/** 更新记账记录(金额/方向/分类/日期/备注) */
export const updateLedgerRecord = (recordId: string, record: LedgerRecordUpdate) => {
  return http_base_server.put<void>(`/site/ledger/records/${recordId}`, record)
}

/** 获取记账记录详情(仅本人可见) */
export const getLedgerRecord = (recordId: string) => {
  return http_base_server.get<LedgerRecord>(`/site/ledger/records/${recordId}`)
}

/** 记账统计(概览 + 支出分类饼图 + 趋势): month 传 YYYY-MM(月度, 近6月趋势) 或 YYYY(年度, 全年12月趋势) */
export const getLedgerStats = (month: string) => {
  return http_base_server.get<LedgerStats>('/site/ledger/records/stats', {
    params: { month },
  })
}

/** 分页查询记账记录(支持月份/方向/分类过滤) */
export const listLedgerRecords = (params: ListLedgerParams) => {
  return http_base_server.get<PaginationResponse<LedgerRecord>>(
    '/site/ledger/records/list',
    { params }
  )
}
