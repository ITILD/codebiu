<template>
  <!-- 版本更新提示按钮(替代弹窗): 检测到服务器版本比当前编译版本新时显示,
       点击整页刷新加载最新静态资源; useVersionCheck 见 app/composables -->
  <button
    v-if="hasNewVersion"
    flex
    items-center
    gap-1
    rounded
    px-3
    py-1.5
    text-sm
    bg-note-tint
    text-note
    hover:shadow-note
    note-transition
    whitespace-nowrap
    @click="reload"
  >
    <el-icon :size="16">
      <Download />
    </el-icon>
    版本已发布点击刷新
  </button>
</template>

<script setup lang="ts">
import { Download } from '@element-plus/icons-vue'
import { useVersionCheck } from '@/app/composables/useVersionCheck'

const { hasNewVersion } = useVersionCheck()

// 整页刷新: 重新请求 index.html, 拿到新版本资源清单
const reload = () => window.location.reload()
</script>
