<template>
  <!-- 有机渐变: 数枚高斯模糊色块各自游走, 叠成流动的"网格渐变", 纯 CSS 无需着色器 -->
  <div class="flex flex-col gap-4 lg:flex-row">
    <div class="og-stage relative h-64 flex-1 overflow-hidden rounded-md border border-[var(--el-border-color-light)] bg-[#12211a]" :style="stageVars">
      <span v-for="(b, i) in blobs" :key="i" class="og-blob absolute rounded-full" :style="blobStyle(b, i)" />
      <span class="pointer-events-none absolute bottom-2 left-3 text-xs text-[#9ec7b8]">色块游走 · 边界在模糊中互相渗透</span>
    </div>

    <!-- 控制面板 -->
    <div class="w-full shrink-0 space-y-1 lg:w-56">
      <div class="flex items-center gap-2">
        <span class="w-14 shrink-0 text-xs text-[var(--el-text-color-secondary)]">糊化</span>
        <el-slider v-model="state.blur" :min="30" :max="110" size="small" class="flex-1" />
      </div>
      <div class="flex items-center gap-2">
        <span class="w-14 shrink-0 text-xs text-[var(--el-text-color-secondary)]">速度</span>
        <el-slider v-model="state.speed" :min="4" :max="16" :step="0.5" size="small" class="flex-1" />
      </div>
      <p class="pt-1 text-xs leading-5 text-[var(--el-text-color-secondary)]">
        每枚色块只是 border-radius: 50% 的纯色圆, filter: blur 把边界融开;
        各圆按不同周期做路径动画, 叠加后即"活的渐变"。设计工具里的 mesh gradient, 本质就是这层窗户纸。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
// 有机渐变(garden.bradwoods.io 渐变类笔记): blur 色块 + 关键帧路径
import type { CSSProperties } from 'vue'

/** 色块定义 */
interface Blob {
  color: string
  /** 静止位置(百分比) */
  x: number
  y: number
  /** 直径(px) */
  size: number
  /** 动画周期倍率(错开节奏) */
  k: number
}

/** 可调参数 */
const state = reactive({ blur: 70, speed: 8 })

/** 色块群: 草木系配色 */
const blobs: Blob[] = [
  { color: '#3f8a5c', x: 8, y: 12, size: 200, k: 1 },
  { color: '#7fb069', x: 52, y: 0, size: 170, k: 1.35 },
  { color: '#d9b45b', x: 30, y: 44, size: 180, k: 0.8 },
  { color: '#2c5d4f', x: 66, y: 40, size: 210, k: 1.15 },
]

/** 舞台级变量 */
const stageVars = computed(() => ({
  '--og-blur': `${state.blur}px`,
  '--og-speed': `${state.speed}s`,
}))

/** 单枚色块样式: 位置/尺寸/动画错拍 */
function blobStyle(b: Blob, i: number): CSSProperties {
  return {
    left: `${b.x}%`,
    top: `${b.y}%`,
    width: `${b.size}px`,
    height: `${b.size}px`,
    background: b.color,
    filter: 'blur(var(--og-blur))',
    animationDuration: `calc(var(--og-speed) * ${b.k})`,
    animationDelay: `${i * -1.7}s`,
  }
}
</script>

<style scoped>
/* 色块沿两条对角线往复游走, alternate 使运动无接缝 */
.og-blob {
  opacity: 0.85;
  animation: og-wander ease-in-out infinite alternate;
  will-change: transform;
}

@keyframes og-wander {
  from { transform: translate(-14%, -10%) scale(1); }
  50% { transform: translate(12%, 6%) scale(1.12); }
  to { transform: translate(-8%, 14%) scale(0.94); }
}
</style>
