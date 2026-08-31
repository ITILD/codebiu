<script setup lang="ts">
import { RouterView } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
// 后台管理页面才显示左侧模块列表, 首页等为纯展示布局(页首+内容+页脚)
const isAdmin = computed(() => route.path.startsWith('/_sys'))

// 应用挂载时为已登录用户刷新权限(修复旧会话持久化的空/过期权限导致菜单被隐藏)
const authStore = useAuthStore()
onMounted(() => {
  if (authStore.authState.user.id) authStore.fetchPermissions()
})
</script>

<template>
  <!-- 整体: 文档流导航 + (后台: 粘性侧边栏 + 主内容) + 页脚(文档末尾)
       注意: 不包 Suspense —— 无组件使用顶层 await, 且 Suspense 会与
       路由 Transition(out-in) 冲突导致切页后视图空白 -->
  <div min-h-screen flex flex-col bg-note-paper>
    <!-- 顶部栏(文档流): 随页面滚动自然移出视野, 不遮挡内容
         Logo/汉堡 + 主题切换 + 登录/头像 -->
    <SysHeader h-14 md:h-16 bg-note-soft border-b border-note shrink-0 />

    <div flex flex-1 items-start>
      <!-- 左侧模块列表(仅后台路由): 滚过导航后钉在视口顶部, 菜单内部滚动 -->
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
