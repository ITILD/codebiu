/**
 * 可见菜单 composable: 按权限码过滤全局菜单树
 * 共用方: SysSidebar(侧边栏/抽屉) / SysBreadcrumb / 主页模块入口卡
 */
import { computed } from 'vue'
import { menuItems } from '@/common/config/menu'
import type { MenuItem } from '@/common/config/menu'
import { usePermission } from './usePermission'

/** 按权限码过滤后的可见菜单(未声明 perm 的项登录即可见) */
export function useVisibleMenu() {
  const { hasPerm } = usePermission()

  const visibleMenuItems = computed<MenuItem[]>(() => {
    return menuItems
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
