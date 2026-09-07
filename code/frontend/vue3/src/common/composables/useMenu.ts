/**
 * 可见菜单 composable: 按权限码过滤菜单树
 * 共用方: SysSidebar(后台侧边栏) / 后台概览页快捷入口 / 头像下拉"后台管理"入口
 * / 首页主应用入口卡(useVisibleApps)
 */
import { computed } from 'vue'
import { adminMenuItems, mainApps } from '@/common/config/menu'
import type { MenuItem } from '@/common/config/menu'
import { usePermission } from './usePermission'
import { useAuthStore } from '@/common/stores/auth'

/** 按权限码过滤后的可见后台菜单(未声明 perm 的项登录即可见) */
export function useVisibleMenu() {
  const { hasPerm } = usePermission()

  const visibleMenuItems = computed<MenuItem[]>(() => {
    return adminMenuItems
      .map((item) => {
        // 目录自身声明了权限码: 无权限直接隐藏整组
        if (item.perm && !hasPerm(item.perm)) return null
        // 子菜单逐项过滤(声明了 perm 的子项需有权限)
        if (item.children) {
          const children = item.children.filter((c) => !c.perm || hasPerm(c.perm))
          if (children.length === 0) return null
          return { ...item, children }
        }
        return item
      })
      .filter((item): item is MenuItem => item !== null)
  })

  return { visibleMenuItems }
}

/**
 * 主应用入口过滤(首页入口卡使用):
 * 未登录全部展示(点击后由路由守卫引导登录); 登录后按权限码过滤,
 * 无权限的主应用不展示入口, 避免进入后接口 401
 */
export function useVisibleApps() {
  const { hasPerm } = usePermission()
  const authStore = useAuthStore()

  const visibleApps = computed<MenuItem[]>(() => {
    // 未登录: 全部展示(主应用是首页门面, 引导登录后使用)
    if (!authStore.authState.user.id) return mainApps
    return mainApps.filter((app) => !app.perm || hasPerm(app.perm))
  })

  return { visibleApps }
}
