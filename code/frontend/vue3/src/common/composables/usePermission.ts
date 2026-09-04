/**
 * 权限判断组合式函数(菜单过滤/按钮级权限控制)
 *
 * 权限码格式与后端注册中心约定一致:
 *   "模块"            目录级,如 "sys"/"rag"
 *   "模块:资源"        菜单级,如 "sys:user"
 *   "模块:资源:动作"   按钮级,如 "sys:user:create"
 *
 * 全局管理员 permissions 为 ["*"],拥有全部权限
 */
import { useAuthStore } from '@/common/stores/auth'

export const usePermission = () => {
  const authStore = useAuthStore()
  const permissions = computed(() => authStore.permState.permissions)

  /** 是否为全局管理员(拥有全部权限) */
  const isAdmin = computed(() => permissions.value.includes('*'))

  /**
   * 判断是否拥有指定权限码
   * - 未登录(无权限数据)时视为无权限
   * - 按钮级权限码("模块:资源:动作")精确匹配
   * - 目录/菜单级权限码("模块" / "模块:资源")只要拥有其任意子权限即视为有权限
   */
  const hasPerm = (code: string): boolean => {
    if (!authStore.authState.user.id) return false
    if (permissions.value.includes('*')) return true
    if (permissions.value.includes(code)) return true
    // 目录/菜单级: 存在以 "code:" 开头的子权限即可见
    return permissions.value.some((p) => p.startsWith(`${code}:`))
  }

  /** 拥有任一权限码即通过 */
  const hasAnyPerm = (codes: string[]): boolean => codes.some((c) => hasPerm(c))

  /**
   * 判断用户在指定域是否拥有角色
   * @param roleKey 角色键,如 "admin"/"rag_user"
   * @param dom 域,默认全局域 "*"
   */
  const hasRole = (roleKey: string, dom = '*'): boolean => {
    return (authStore.permState.roles[dom] || []).includes(roleKey)
  }

  return { permissions, isAdmin, hasPerm, hasAnyPerm, hasRole }
}
