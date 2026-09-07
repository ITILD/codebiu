<template>
  <!-- 知识库模块内页导航: 应用页无侧边栏, 孙页面关系由此承担(按权限过滤) -->
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
      :class="isActive(tab.index)
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
import { Collection, Document, User, ChatDotRound } from '@element-plus/icons-vue'
import { usePermission } from '@/common/composables/usePermission'

/** 知识库模块孙页面定义(perm 与菜单配置一致, 无权限不显示入口) */
const tabs = [
  { index: '/rag/project', title: '知识库管理', icon: markRaw(Collection), perm: 'rag:project' },
  { index: '/rag/document', title: '文档管理', icon: markRaw(Document), perm: 'rag:doc' },
  { index: '/rag/member', title: '成员管理', icon: markRaw(User), perm: 'rag:member' },
  { index: '/rag/conversation', title: '知识库问答', icon: markRaw(ChatDotRound), perm: 'rag:chat' },
]

const route = useRoute()
const { hasPerm } = usePermission()

const visibleTabs = computed(() => tabs.filter((t) => !t.perm || hasPerm(t.perm)))

/** 当前页高亮(文档/成员页从项目卡跳入, 按路径前缀匹配) */
function isActive(index: string): boolean {
  return route.path === index || route.path.startsWith(`${index}/`)
}
</script>
