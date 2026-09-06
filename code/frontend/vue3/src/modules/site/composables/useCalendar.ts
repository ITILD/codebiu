// src/modules/site/composables/useCalendar.ts —— 日历日期工具(原生 Date, 免依赖)
// 提供 年/月/周 三种视图的网格计算与后端 range 查询边界(本地时区 ISO)

/** 视图模式 */
export type CalendarView = 'year' | 'month' | 'week'

/** 日历单元格(月网格/年网格用) */
export interface CalendarCell {
  date: Date
  /** 是否属于当前聚焦月(月网格中非当月日置灰) */
  inMonth: boolean
}

const pad = (n: number) => String(n).padStart(2, '0')

/** 本地日期键 YYYY-MM-DD(日历分组依据) */
export function dateKey(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/** 本地时区 ISO 时间(当天 00:00), 保证后端按本地日历日过滤 */
export function localIsoStartOfDay(d: Date): string {
  const off = -d.getTimezoneOffset()
  const sign = off >= 0 ? '+' : '-'
  const oh = pad(Math.floor(Math.abs(off) / 60))
  const om = pad(Math.abs(off) % 60)
  return `${dateKey(d)}T00:00:00${sign}${oh}:${om}`
}

/** 本地时区 ISO 时间(当天 24:00 = 次日 00:00) */
export function localIsoEndOfDay(d: Date): string {
  const next = new Date(d)
  next.setDate(next.getDate() + 1)
  return localIsoStartOfDay(next)
}

/** 所在周的周一 00:00(周视图从周一开始) */
export function startOfWeek(d: Date): Date {
  const Monday = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const day = Monday.getDay() === 0 ? 7 : Monday.getDay() // 周日=0 → 7
  Monday.setDate(Monday.getDate() - (day - 1))
  return Monday
}

/** 月网格: 6周×7天(含前后月补位), 从当月1日所在周的周一开始 */
export function monthGrid(year: number, month: number): CalendarCell[] {
  const first = new Date(year, month - 1, 1)
  const gridStart = startOfWeek(first)
  const cells: CalendarCell[] = []
  for (let i = 0; i < 42; i++) {
    const d = new Date(gridStart)
    d.setDate(gridStart.getDate() + i)
    cells.push({ date: d, inMonth: d.getMonth() === month - 1 })
  }
  return cells
}

/** 月视图 range 边界: [当月1日, 下月1日) */
export function monthRange(year: number, month: number): [string, string] {
  return [
    localIsoStartOfDay(new Date(year, month - 1, 1)),
    localIsoStartOfDay(new Date(year, month, 1)),
  ]
}

/** 年视图 range 边界: [1月1日, 次年1月1日) */
export function yearRange(year: number): [string, string] {
  return [localIsoStartOfDay(new Date(year, 0, 1)), localIsoStartOfDay(new Date(year + 1, 0, 1))]
}

/** 周视图 range 边界: [本周一, 下周一) */
export function weekRange(anchor: Date): [string, string] {
  const monday = startOfWeek(anchor)
  const nextMonday = new Date(monday)
  nextMonday.setDate(monday.getDate() + 7)
  return [localIsoStartOfDay(monday), localIsoStartOfDay(nextMonday)]
}

/** 周视图的7天(周一~周日) */
export function weekDays(anchor: Date): Date[] {
  const monday = startOfWeek(anchor)
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday)
    d.setDate(monday.getDate() + i)
    return d
  })
}

/** 年视图的12个月首日 */
export function yearMonths(year: number): Date[] {
  return Array.from({ length: 12 }, (_, i) => new Date(year, i, 1))
}

/** 当前视图的 range 边界 */
export function viewRange(view: CalendarView, anchor: Date): [string, string] {
  const y = anchor.getFullYear()
  const m = anchor.getMonth() + 1
  if (view === 'year') return yearRange(y)
  if (view === 'month') return monthRange(y, m)
  return weekRange(anchor)
}

/** 视图标题 */
export function viewTitle(view: CalendarView, anchor: Date): string {
  const y = anchor.getFullYear()
  const m = anchor.getMonth() + 1
  if (view === 'year') return `${y}年`
  if (view === 'month') return `${y}年${m}月`
  const days = weekDays(anchor)
  return `${y}年${m}月 ${dateKey(days[0]).slice(5)} ~ ${dateKey(days[6]).slice(5)}`
}

/** 备忘全文摘录(前 limit 字) */
export function excerpt(text: string | null | undefined, limit = 200): string {
  if (!text) return ''
  return text.length > limit ? `${text.slice(0, limit)}…` : text
}

/** 将备忘列表按本地日期键分组 */
export function groupByDate<T extends { start_at: string }>(
  items: T[]
): Map<string, T[]> {
  const map = new Map<string, T[]>()
  for (const item of items) {
    // start_at 为 ISO 字符串, 按本地时间取日期键
    const key = dateKey(new Date(item.start_at))
    const list = map.get(key)
    if (list) list.push(item)
    else map.set(key, [item])
  }
  return map
}
