<template>
  <!-- 纸张质感卡片: overlay 混合配方演示(噪声 + 内阴影 + 渐晕与纸色混合) -->
  <div class="flex flex-col gap-4 lg:flex-row">
    <!-- 参数控制面板 -->
    <div class="w-full shrink-0 space-y-1 lg:w-64">
      <div v-for="c in controls" :key="c.key" class="flex items-center gap-2">
        <span class="w-20 shrink-0 text-xs text-[var(--el-text-color-secondary)]">{{ c.label }}</span>
        <el-slider v-model="state[c.key]" :min="c.min" :max="c.max" :step="c.step ?? 1" size="small" />
      </div>
      <el-checkbox v-model="blended" size="small">启用 overlay 混合</el-checkbox>
      <p class="text-xs leading-5 text-[var(--el-text-color-secondary)]">
        overlay 让暗色更暗、亮色更亮，50% 灰不受影响。悬停下方按钮试试 —— 顶盖纹理会同样"印"到按钮上。
      </p>
    </div>

    <!-- 纸张演示: 内容夹在纸色底层与 overlay 顶盖之间 -->
    <div
      class="relative isolate min-h-56 flex-1 overflow-hidden rounded-md"
      :style="{ background: `hsl(${state.hue}, ${state.sat}%, ${state.light}%)` }"
    >
      <div class="relative z-10 flex h-full min-h-56 flex-col items-start justify-center gap-3 p-6">
        <h4 class="text-lg font-bold" style="color: hsl(140, 25%, 24%)">园艺手记 · 第 47 页</h4>
        <p class="max-w-sm text-sm leading-6" style="color: hsl(140, 15%, 34%)">
          噪声纹理、角落渐晕与内阴影通过 mix-blend-mode: overlay 与底层纸色混合，得到纤维纸面质感。
        </p>
        <el-button type="primary" @click="pressed = !pressed">{{ pressed ? '被按过啦' : '按我试试' }}</el-button>
      </div>
      <!-- overlay 顶盖: 与其下所有像素(含内容)混合; pointer-events 放行鼠标 -->
      <div class="pointer-events-none absolute inset-0 z-20" :style="overlayStyle" />
    </div>
  </div>
</template>

<script setup lang="ts">
// 纸张效果(garden.bradwoods.io/notes/css/blend-modes#paper):
// base 层 hsl 纸色 + 顶层 overlay(噪声图 + 线性渐晕 + inset 阴影), 可调参数实时预览
import { NOISE_URL } from './texture'
import type { CSSProperties } from 'vue'

/** 滑杆配置 */
interface SliderConf {
  key: 'hue' | 'sat' | 'light' | 'blur' | 'spread' | 'opacity' | 'grad'
  label: string
  min: number
  max: number
  step?: number
}

/** 控制项(默认值取自原笔记示例) */
const controls: SliderConf[] = [
  { key: 'hue', label: '色相', min: 0, max: 360 },
  { key: 'sat', label: '饱和度', min: 0, max: 100 },
  { key: 'light', label: '明度', min: 40, max: 95 },
  { key: 'blur', label: '阴影模糊', min: 0, max: 80 },
  { key: 'spread', label: '阴影扩展', min: 0, max: 30 },
  { key: 'opacity', label: '阴影浓度', min: 0, max: 1, step: 0.05 },
  { key: 'grad', label: '渐晕起点', min: 0, max: 90 },
]

/** 可调参数集合 */
const state = reactive<Record<string, number>>({
  hue: 40, sat: 35, light: 76,
  blur: 40, spread: 10, opacity: 0.45, grad: 40,
})

/** 是否启用混合(关闭后可对比"无混合"的生硬效果) */
const blended = ref(true)

/** 演示按钮状态 */
const pressed = ref(false)

/** overlay 顶盖样式: 噪声 + 渐晕渐变 + inset 阴影 */
const overlayStyle = computed<CSSProperties>(() => ({
  boxShadow: `inset 0 0 ${state.blur}px ${state.spread}px hsla(0, 0%, 0%, ${state.opacity})`,
  background: `${NOISE_URL}, linear-gradient(to bottom right, hsla(0, 0%, 0%, 0) ${state.grad}%, hsla(0, 0%, 0%, 1) 130%)`,
  mixBlendMode: blended.value ? 'overlay' : 'normal',
}))
</script>
