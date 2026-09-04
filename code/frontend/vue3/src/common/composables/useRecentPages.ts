/**
 * 最近访问页面记录 composable(localStorage 持久化)
 * 条目: { path, title, ts }, 按访问时间倒序, 上限 8 条
 * 采集点: App.vue watch route.path(仅 admin 路由), 主页/后台页读取展示
 */
import { useLocalStorage } from '@vueuse/core'

/** 单条最近访问记录 */
export interface RecentPage {
  path: string
  title: string
  /** 最后访问时间戳(ms) */
  ts: number
}

const KEY = 'note:recent-pages'
/** 上限条数 */
const MAX_COUNT = 8

/** 最近访问列表(响应式, localStorage 同步) */
const recentPages = useLocalStorage<RecentPage[]>(KEY, [])

/** 记录一次页面访问: 同 path 去重后插入头部 */
function pushRecent(path: string, title: string) {
  // 首页/空路径不记录
  if (!path || path === '/') return
  recentPages.value = [
    { path, title, ts: Date.now() },
    ...recentPages.value.filter((p) => p.path !== path),
  ].slice(0, MAX_COUNT)
}

export function useRecentPages() {
  return { recentPages, pushRecent }
}
