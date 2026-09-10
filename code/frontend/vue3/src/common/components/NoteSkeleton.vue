<script setup lang="ts">
/**
 * 通用骨架屏: 接口数据到达前占位, 保持与真实内容相近的尺寸, 防 CLS 抖动。
 * variant: post 文章卡 / table 表格 / stat 概览条 / list 列表行 / paragraph 文本段 / block 通用块
 */
interface Props {
  variant?: 'post' | 'table' | 'stat' | 'list' | 'paragraph' | 'block'
  /** 重复行数(表格行/列表行/文本行) */
  rows?: number
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'block',
  rows: 5,
})
</script>

<template>
  <!-- 文章卡片骨架: 与博客列表卡(p-4, 标题+两行摘要+元信息)同尺寸 -->
  <div
    v-if="variant === 'post'"
    class="rounded-xl border border-note/50 bg-note-card shadow-note p-4 overflow-hidden"
    aria-hidden="true"
  >
    <div class="flex items-center gap-2">
      <div class="note-sk h-4 w-2/5" />
      <div class="note-sk h-3.5 w-3.5 note-sk-circle" />
    </div>
    <div class="note-sk mt-2.5 h-3.5 w-11/12" />
    <div class="note-sk mt-2 h-3.5 w-3/5" />
    <div class="mt-3 flex items-center gap-2">
      <div class="note-sk h-5 w-14 rounded-full" />
      <div class="note-sk h-3 w-16" />
    </div>
  </div>

  <!-- 表格骨架: 表头 + 若干数据行 -->
  <div v-else-if="variant === 'table'" class="w-full" aria-hidden="true">
    <div class="flex items-center gap-3 px-3 py-2.5">
      <div v-for="i in Math.min(rows, 6)" :key="i" class="note-sk h-3.5 flex-1" />
    </div>
    <div
      v-for="r in rows"
      :key="r"
      class="flex items-center gap-3 border-t border-note/40 px-3 py-3"
    >
      <div v-for="i in Math.min(rows, 6)" :key="i" class="h-3 flex-1">
        <div class="note-sk h-full" :class="i === 1 ? 'w-4/5' : i % 2 ? 'w-2/3' : 'w-3/4'" />
      </div>
    </div>
  </div>

  <!-- 概览统计条骨架: 数值位置与真实 chip 等高 -->
  <div v-else-if="variant === 'stat'" class="flex flex-col gap-1.5" aria-hidden="true">
    <div class="note-sk h-3 w-16" />
    <div class="note-sk h-6 w-12" />
    <div class="note-sk h-3 w-20" />
  </div>

  <!-- 列表行骨架: 圆点 + 两行文字 -->
  <div v-else-if="variant === 'list'" class="w-full space-y-4" aria-hidden="true">
    <div v-for="r in rows" :key="r" class="flex items-center gap-3">
      <div class="note-sk note-sk-circle h-8 w-8 shrink-0" />
      <div class="min-w-0 flex-1 space-y-2">
        <div class="note-sk h-3.5 w-1/3" />
        <div class="note-sk h-3 w-2/5" />
      </div>
    </div>
  </div>

  <!-- 文本段落骨架: 参差行宽更接近真实文字 -->
  <div v-else-if="variant === 'paragraph'" class="w-full space-y-2.5" aria-hidden="true">
    <div
      v-for="r in rows"
      :key="r"
      class="note-sk h-3.5"
      :class="r === rows ? 'w-2/5' : r % 3 === 0 ? 'w-11/12' : 'w-full'"
    />
  </div>

  <!-- 通用矩形块 -->
  <div v-else class="note-sk w-full" :style="{ height: '120px' }" aria-hidden="true" />
</template>
