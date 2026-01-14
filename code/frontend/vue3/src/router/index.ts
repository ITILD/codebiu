import { createRouter, createWebHistory } from 'vue-router'
/**
 * 自动路由
 * 原本routes更换
 * 路由规则 https://uvr.esm.is/guide/file-based-routing.html
 */
import { routes, handleHotUpdate } from "vue-router/auto-routes"
import { RouterStore } from '@/stores/router'
import { SysSettingStore } from '@/stores/sys'
// 生成路由  注意nginx发布配置 添加跳转
const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: routes
})

// 路由监听
router.beforeEach((to, from, next) => {
  // 在导航守卫的回调函数内部调用 useStore() 防止在 ​​Pinia 初始化之前​​ 使用 store
  console.log(`router.beforeEach path from ${from.path} to ${to.path} `)
  if(to.path === '/setting'){
    // 页首页尾动画隐藏
    const sysSettingStore = SysSettingStore()
    sysSettingStore.sysStyle.headFootShow = false
  }else{
    // 页首页尾动画显示
    const sysSettingStore = SysSettingStore()
    sysSettingStore.sysStyle.headFootShow = true
  }

  const routerStore = RouterStore()
  routerStore.setRouterPath(to.path)
  next()
  console.log(routerStore.routerPath.now)
})

// 开发模式
if (import.meta.env.DEV) {
  console.log('开发模式')
  // 热更新并刷新路由
  if (import.meta.hot) handleHotUpdate(router)
}



export default router
