<script setup lang="ts">
import { RouterView } from 'vue-router'
import { useAuthStore } from '@/common/stores/auth'
import { useRecentPages } from '@/common/composables/useRecentPages'
import { findMenuTrail } from '@/common/config/menu'

const route = useRoute()
// 后台管理页面才显示左侧模块列表, 首页等为纯展示布局(页首+内容+页脚)
// admin 标记由 vite.config.ts 的 extendRoute 写入路由 meta
const isAdmin = computed(() => Boolean(route.meta.admin))

// 最近访问采集: 仅记录后台路由(登录后才有意义), 标题取菜单树末级
const { pushRecent } = useRecentPages()
watch(
  () => route.path,
  (path) => {
    if (!route.meta.admin) return
    // 兼容 es2020 lib: 用索引取末级而非 Array.prototype.at
    const trail = findMenuTrail(path)
    const title = trail.length > 0 ? trail[trail.length - 1].title : path
    pushRecent(path, title)
  }
)

// 应用挂载时为已登录用户刷新权限(修复旧会话持久化的空/过期权限导致菜单被隐藏)
const authStore = useAuthStore()
onMounted(() => {
  if (authStore.authState.user.id) authStore.fetchPermissions()
})
</script>

<template>
  <!-- 整体: 吸顶导航 + (后台: 粘性侧边栏 + 主内容) + 页脚(文档末尾)
       注意: 不包 Suspense —— 无组件使用顶层 await, 且 Suspense 会与
       路由 Transition(out-in) 冲突导致切页后视图空白 -->
  <div min-h-screen flex flex-col bg-note-paper>
    <!-- 顶部栏(吸顶+毛玻璃): 滚动时钉在视口顶部
         注意: bg-note-glass 含方括号任意值, 必须写进 class 属性(attributify 陷阱)
         高度保持 h-14 md:h-16 不变 —— h-app/max-h-app 公式与侧边栏 top-16 依赖它 -->
    <SysHeader
      class="sticky top-0 z-20 h-14 md:h-16 border-b border-note shrink-0 bg-note-glass backdrop-blur-md"
    />

    <div flex flex-1 items-start>
      <!-- 左侧模块列表(仅后台路由): 钉在吸顶导航下方, 菜单内部滚动 -->
      <SysSidebar v-if="isAdmin" />

      <!-- 主内容区: 文档流自然滚动
           注意: 此处不要用 Transition 包裹路由组件 —— 与路由懒加载组件
           组合存在组件更新时 parentNode(null) 的空白 bug(out-in 与交叉
           淡入两种模式均已踩坑), 故直接渲染 RouterView 保证稳定 -->
      <main flex-1 min-w-0 w-full>
        <RouterView />
      </main>
    </div>

    <!-- 页脚: 位于文档末尾, 随内容增长 -->
    <SysFooter w-full shrink-0 />
  </div>
</template>

<style>
/* 说明: 路由切换过渡已移除 —— Transition 与路由懒加载组件组合
   存在组件更新时 parentNode(null) 导致整页空白的 bug */
</style>
