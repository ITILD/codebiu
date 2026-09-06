<template>
  <!-- 图案工厂: 仅用 CSS 渐变函数"织"出条纹/网点/棋盘/网格/人字五种图案 -->
  <div class="flex flex-col gap-4 lg:flex-row">
    <div class="relative h-64 flex-1 overflow-hidden rounded-md border border-[var(--el-border-color-light)]">
      <div class="h-full w-full" :style="patternStyle" />
      <span class="pointer-events-none absolute bottom-2 left-3 text-xs text-[var(--el-text-color-secondary)]">零图片 · 纯渐变函数平铺</span>
    </div>

    <!-- 控制面板 -->
    <div class="w-full shrink-0 space-y-2 lg:w-56">
      <el-segmented v-model="state.kind" :options="kindOptions" size="small" class="w-full" />
      <div class="flex items-center gap-2">
        <span class="w-14 shrink-0 text-xs text-[var(--el-text-color-secondary)]">尺寸</span>
        <el-slider v-model="state.size" :min="8" :max="48" size="small" class="flex-1" />
      </div>
      <div class="flex items-center gap-2">
        <span class="w-14 shrink-0 text-xs text-[var(--el-text-color-secondary)]">角度</span>
        <el-slider v-model="state.angle" :min="0" :max="90" size="small" class="flex-1" :disabled="state.kind !== 'stripes'" />
      </div>
      <div class="flex items-center gap-2">
        <span class="w-8 shrink-0 text-xs text-[var(--el-text-color-secondary)]">主色</span>
        <el-color-picker v-model="state.c1" size="small" />
        <span class="w-8 shrink-0 text-xs text-[var(--el-text-color-secondary)]">副色</span>
        <el-color-picker v-model="state.c2" size="small" />
      </div>
      <p class="pt-1 text-xs leading-5 text-[var(--el-text-color-secondary)]">
        repeating-linear-gradient 平铺条纹; radial-gradient 画圆点; conic-gradient 四象限拼棋盘;
        两组正交 linear-gradient 叠出网格; 两层斜向 repeating 渐变错相即人字纹。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
// CSS 图案(garden.bradwoods.io/notes/css/gradients):
// 渐变函数本身可平铺(background-repeat), 颜色断点处"硬切"即得几何图案
import type { CSSProperties } from 'vue'

/** 图案类型 */
type PatternKind = 'stripes' | 'dots' | 'checker' | 'grid' | 'zigzag'

/** 可调参数 */
const state = reactive<{ kind: PatternKind; size: number; angle: number; c1: string; c2: string }>({
  kind: 'stripes',
  size: 20,
  angle: 45,
  c1: '#4a7c59',
  c2: '#f2efe6',
})

/** 类型选项 */
const kindOptions = [
  { label: '条纹', value: 'stripes' },
  { label: '网点', value: 'dots' },
  { label: '棋盘', value: 'checker' },
  { label: '网格', value: 'grid' },
  { label: '人字', value: 'zigzag' },
]

/** 按类型生成图案背景样式 */
const patternStyle = computed<CSSProperties>(() => {
  const { kind, size, angle, c1, c2 } = state
  const half = size / 2
  const map: Record<PatternKind, CSSProperties> = {
    // 条纹: 硬断点双向平铺
    stripes: {
      background: `repeating-linear-gradient(${angle}deg, ${c1} 0 ${half}px, ${c2} ${half}px ${size}px)`,
    },
    // 网点: 圆点 + 透明底
    dots: {
      backgroundColor: c2,
      backgroundImage: `radial-gradient(circle at center, ${c1} ${size * 0.28}px, transparent ${size * 0.3}px)`,
      backgroundSize: `${size * 1.6}px ${size * 1.6}px`,
    },
    // 棋盘: conic 四象限, 两格为一周期
    checker: {
      background: `conic-gradient(${c1} 90deg, ${c2} 0 180deg, ${c1} 0 270deg, ${c2} 0)`,
      backgroundSize: `${size * 2}px ${size * 2}px`,
    },
    // 网格: 两组正交细线
    grid: {
      backgroundColor: c2,
      backgroundImage: `linear-gradient(${c1} 1px, transparent 1px), linear-gradient(90deg, ${c1} 1px, transparent 1px)`,
      backgroundSize: `${size}px ${size}px`,
    },
    // 人字纹: 两个斜向渐变各取半周期
    zigzag: {
      backgroundColor: c2,
      backgroundImage: `repeating-linear-gradient(45deg, ${c1} 0 ${half * 0.7}px, transparent ${half * 0.7}px ${half * 1.4}px), repeating-linear-gradient(-45deg, ${c1} 0 ${half * 0.7}px, transparent ${half * 0.7}px ${half * 1.4}px)`,
    },
  }
  return map[kind]
})
</script>
