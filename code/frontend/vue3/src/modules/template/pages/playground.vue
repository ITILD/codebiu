<template>
  <div p-2 md:p-4>
    <!-- 页头 -->
    <div mb-4>
      <h2 text-xl font-bold text-note>组件选型 Playground</h2>
      <p text-sm text-note-sub mt-1>同一套常用组件套用不同主题皮肤，每个主题为独立子页面，用于前端样式选型。</p>
    </div>

    <!-- 主题切换导航(父壳路由导航, 首项为主题总览) -->
    <nav mb-4 flex flex-wrap gap-2>
      <el-button v-for="t in navItems" :key="t.path" size="small"
        :type="route.path === t.path ? 'primary' : 'default'" @click="router.push(t.path)">
        {{ t.name }}
      </el-button>
    </nav>

    <!-- 主题子页面(总览卡片 / 各主题展示页) -->
    <RouterView />
  </div>
</template>

<script setup lang="ts">
// 组件选型父壳: 主题切换导航 + 嵌套子页面(主题总览与各主题展示页)
import { playgroundThemes } from '../components/playground/themes'

const route = useRoute()
const router = useRouter()

// 导航项: 主题总览 + 各主题
const navItems = [
  { path: '/template/playground', name: '主题总览' },
  ...playgroundThemes.map((t) => ({ path: t.path, name: t.name })),
]
</script>
