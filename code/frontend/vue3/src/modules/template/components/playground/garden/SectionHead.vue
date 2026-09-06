<template>
  <!-- 区块标题头: 技巧名 + 技术标签 + 原站笔记来源链接 -->
  <div class="flex flex-wrap items-center gap-2">
    <span class="font-semibold">{{ title }}</span>
    <el-tag size="small" type="success" effect="plain">{{ tag }}</el-tag>
    <a
      class="ml-auto text-xs text-[var(--el-color-primary)] hover:underline"
      :href="href"
      target="_blank"
      rel="noopener"
    >
      来源笔记 ↗
    </a>
  </div>
</template>

<script setup lang="ts">
// 区块标题头: 统一各演示卡片头部的排版
defineProps<{
  /** 技巧名称 */
  title: string
  /** 技术要点标签 */
  tag: string
  /** 原站笔记链接 */
  href: string
}>()
</script>
