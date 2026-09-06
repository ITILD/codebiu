<template>
  <!-- 位移缩放: 悬停放大图像, feTurbulence + feDisplacementMap 让边缘如液体般流动 -->
  <div class="flex flex-col gap-4 lg:flex-row">
    <div
      class="relative h-64 flex-1 cursor-zoom-in overflow-hidden rounded-md border border-[var(--el-border-color-light)] bg-[var(--el-fill-color-light)]"
      @mouseenter="tween(state.liquid)"
      @mouseleave="tween(0)"
    >
      <svg class="h-full w-full" viewBox="0 0 400 300" preserveAspectRatio="xMidYMid slice" role="img" aria-label="液态缩放演示">
        <defs>
          <filter id="gdn-liquid" x="-15%" y="-15%" width="130%" height="130%">
            <feTurbulence type="fractalNoise" baseFrequency="0.012 0.02" numOctaves="2" seed="4" result="noise" />
            <feDisplacementMap in="SourceGraphic" in2="noise" :scale="disp" xChannelSelector="R" yChannelSelector="G" />
          </filter>
        </defs>
        <image
          :href="mainPhoto"
          x="0"
          y="0"
          width="400"
          height="300"
          preserveAspectRatio="xMidYMid slice"
          filter="url(#gdn-liquid)"
          class="liquid-img"
          :style="{ transform: `scale(${hovered ? state.zoom : 1})` }"
        />
      </svg>
      <span class="pointer-events-none absolute bottom-2 left-3 text-xs text-[var(--el-text-color-secondary)]">悬停放大 · 边缘液化流动(rAF 补间)</span>
    </div>

    <!-- 控制面板 -->
    <div class="w-full shrink-0 space-y-1 lg:w-56">
      <div class="flex items-center gap-2">
        <span class="w-14 shrink-0 text-xs text-[var(--el-text-color-secondary)]">液化</span>
        <el-slider v-model="state.liquid" :min="10" :max="80" size="small" class="flex-1" />
      </div>
      <div class="flex items-center gap-2">
        <span class="w-14 shrink-0 text-xs text-[var(--el-text-color-secondary)]">缩放</span>
        <el-slider v-model="state.zoom" :min="1" :max="1.4" :step="0.02" size="small" class="flex-1" />
      </div>
      <p class="pt-1 text-xs leading-5 text-[var(--el-text-color-secondary)]">
        CSS scale 负责平滑放大, feDisplacementMap 负责把像素按噪声场推挤; 悬停时用 rAF 把位移强度从 0 补间到目标值,
        液化便"呼吸"般浮现而不是生硬切换。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
// SVG 滤镜(garden.bradwoods.io/notes/svg/filters) + CSS transform 缩放的组合技巧
import { mainPhoto } from './texture'

/** 可调参数 */
const state = reactive({ liquid: 36, zoom: 1.16 })

/** 是否悬停(决定缩放档位) */
const hovered = ref(false)

/** 当前位移强度(经 rAF 补间, 平滑过渡) */
const disp = ref(0)

/** 补间动画句柄 */
let raf = 0

/** 悬停/离开: 记录状态并补间位移强度 */
function tween(target: number) {
  hovered.value = target > 0
  cancelAnimationFrame(raf)
  const from = disp.value
  const t0 = performance.now()
  const dur = 500
  const step = (t: number) => {
    const p = Math.min(1, (t - t0) / dur)
    const e = 1 - Math.pow(1 - p, 3) // easeOutCubic
    disp.value = from + (target - from) * e
    if (p < 1) raf = requestAnimationFrame(step)
  }
  raf = requestAnimationFrame(step)
}

onBeforeUnmount(() => cancelAnimationFrame(raf))
</script>

<style scoped>
/* SVG <image> 的 transform 需要 fill-box 参照, 否则缩放中心默认在画布原点 */
.liquid-img {
  transform-box: fill-box;
  transform-origin: center;
  transition: transform 0.6s cubic-bezier(0.22, 1, 0.36, 1);
}
</style>
