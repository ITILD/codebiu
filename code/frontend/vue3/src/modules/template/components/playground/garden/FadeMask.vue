<template>
  <!-- 渐隐融入: mask 线性渐变让图片边缘淡出到纸张底色, 支持 4 种方向 -->
  <div class="flex flex-col gap-4 lg:flex-row">
    <div class="relative h-64 flex-1 overflow-hidden rounded-md border border-[var(--el-border-color-light)] bg-[var(--el-fill-color-light)]">
      <img
        :src="mainPhoto"
        alt="渐隐融合演示"
        class="h-full w-full object-cover"
        :style="fadeStyle"
        loading="lazy"
        decoding="async"
      />
      <span class="pointer-events-none absolute bottom-2 left-3 text-xs text-[var(--el-text-color-secondary)]">图片边缘正在"溶"进纸张</span>
    </div>

    <!-- 控制面板 -->
    <div class="w-full shrink-0 space-y-2 lg:w-56">
      <div class="flex items-center gap-2">
        <span class="w-14 shrink-0 text-xs text-[var(--el-text-color-secondary)]">起始%</span>
        <el-slider v-model="state.start" :min="20" :max="80" size="small" class="flex-1" />
      </div>
      <el-segmented v-model="state.dir" :options="dirOptions" size="small" class="w-full" />
      <p class="pt-1 text-xs leading-5 text-[var(--el-text-color-secondary)]">
        mask-image 的线性渐变从黑色(完全显示)过渡到透明(完全隐藏),
        图片边缘便与下方背景无缝融合 —— 横幅配图、卡片头图常用它避免"生硬的矩形边"。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
// CSS mask 渐隐(garden.bradwoods.io/notes/svg/mask):
// mask 渐变的 alpha 通道决定显隐, 与 opacity 不同的是只作用于被遮区域, 不影响布局
import type { CSSProperties } from 'vue'
import { mainPhoto } from './texture'

/** 渐隐方向 */
type FadeDir = 'bottom' | 'right' | 'radial'

/** 可调参数 */
const state = reactive<{ start: number; dir: FadeDir }>({ start: 55, dir: 'bottom' })

/** 方向选项(带中文标签) */
const dirOptions = [
  { label: '底部', value: 'bottom' },
  { label: '右侧', value: 'right' },
  { label: '四周', value: 'radial' },
]

/** 按方向生成 mask 渐变样式 */
const fadeStyle = computed<CSSProperties>(() => {
  const s = `${state.start}%`
  const masks: Record<FadeDir, string> = {
    bottom: `linear-gradient(to bottom, #000 ${s}, transparent 100%)`,
    right: `linear-gradient(to right, #000 ${s}, transparent 100%)`,
    radial: `radial-gradient(ellipse 90% 85% at center, #000 45%, transparent 98%)`,
  }
  const g = masks[state.dir]
  return { maskImage: g, WebkitMaskImage: g }
})
</script>
