import { createRouter, createWebHistory } from 'vue-router'
/**
 * 自动路由
 * 原本routes更换
 * 路由规则 https://uvr.esm.is/guide/file-based-routing.html
 */
import { routes, handleHotUpdate } from "vue-router/auto-routes"
import { RouterStore } from '@/common/stores/router'
import { useAuthStore } from '@/common/stores/auth'
import { ElMessage } from 'element-plus'

// 路由 meta 类型扩展(admin 由 vite.config.ts 的 extendRoute 统一标记:
// 首页与 404 为公开页, 后台工作台/账户设置/各模块页面均为后台路由)
declare module 'vue-router' {
  interface RouteMeta {
    /** 后台管理路由: 需登录访问, 且显示左侧模块列表 */
    admin?: boolean
  }
}

// 生成路由  注意nginx发布配置 添加跳转
const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: routes
})

// 路由监听
router.beforeEach((to, from, next) => {
  const routerStore = RouterStore()
  routerStore.setRouterPath(to.path)
  // 后台管理需要登录: 未登录访问后台路由(meta.admin)时回到首页并引导登录
  const authStore = useAuthStore()
  if (to.meta.admin && !authStore.authState.user.id) {
    ElMessage.warning('请先登录后再访问后台管理')
    next({ path: '/', query: { login: '1' } })
    return
  }
  next()
})

// 开发模式
if (import.meta.env.DEV) {
  console.log('开发模式')
  // 热更新并刷新路由
  if (import.meta.hot) handleHotUpdate(router)
}

export default router
