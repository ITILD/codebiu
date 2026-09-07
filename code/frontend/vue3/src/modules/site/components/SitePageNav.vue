<template>
  <!-- 个人小站模块内页导航: 应用页无侧边栏, 孙页面关系由此承担(按权限过滤) -->
  <nav flex flex-wrap items-center gap-2>
    <RouterLink
      v-for="tab in visibleTabs"
      :key="tab.index"
      :to="tab.index"
      flex
      items-center
      gap-1.5
      px-3.5
      py-1.5
      rounded-full
      border
      border-note
      text-sm
      transition-colors
      :class="route.path === tab.index
        ? 'bg-note-green text-white border-note-green font-medium'
        : 'bg-note-card text-note hover:border-note-green hover:text-note-green'"
    >
      <el-icon :size="14"><component :is="tab.icon" /></el-icon>
      {{ tab.title }}
    </RouterLink>
  </nav>
</template>

<script setup lang="ts">
import { markRaw, computed } from 'vue'
import { useRoute } from 'vue-router'
import { Notebook, Reading } from '@element-plus/icons-vue'
import { usePermission } from '@/common/composables/usePermission'

/** 个人小站模块孙页面定义(perm 与菜单配置一致, 无权限不显示入口) */
const tabs = [
  { index: '/site', title: '工作台', icon: markRaw(Notebook), perm: 'site' },
  { index: '/site/blog_view', title: '博客展示', icon: markRaw(Reading), perm: 'site:blog' },
]

const route = useRoute()
const { hasPerm } = usePermission()

const visibleTabs = computed(() => tabs.filter((t) => !t.perm || hasPerm(t.perm)))
</script>
