// src/modules/site/types/ledger.ts —— 记账类型

/** 收支方向: 收入 / 支出 */
export type LedgerFlow = 'income' | 'expense'

/** 记账记录实体 */
export interface LedgerRecord {
  id: string
  user_id: string
  /** 金额(元) */
  amount: number
  flow_type: LedgerFlow
  /** 分类(餐饮/交通/工资等) */
  category: string
  note: string | null
  /** 记账日期(YYYY-MM-DD) */
  occurred_at: string
  created_at: string
  updated_at: string
}

/** 创建记账记录参数 */
export interface LedgerRecordCreate {
  amount: number
  flow_type?: LedgerFlow
  category: string
  note?: string | null
  /** 记账日期(YYYY-MM-DD), 缺省今天 */
  occurred_at?: string
}

/** 更新记账记录参数(全部可选, 仅更新传入字段) */
export type LedgerRecordUpdate = Partial<LedgerRecordCreate>

/** 支出分类统计(饼图数据项) */
export interface CategoryStat {
  category: string
  total: number
  count: number
}

/** 月度收支趋势(柱状图数据项) */
export interface MonthTrend {
  /** YYYY-MM */
  month: string
  income: number
  expense: number
}

/** 记账统计响应(月度或年度) */
export interface LedgerStats {
  /** 统计周期 YYYY-MM(月度) 或 YYYY(年度) */
  month: string
  income_total: number
  expense_total: number
  balance: number
  /** 周期内支出分类占比(饼图) */
  category_pie: CategoryStat[]
  /** 收支趋势(月度近6月 / 年度全年12月, 含统计周期) */
  trend: MonthTrend[]
}
