<template>
  <!-- 涟漪水面: SMIL 动画驱动 feTurbulence 基频往复波动, feDisplacementMap 把图像按噪声场扭曲 -->
  <div class="flex flex-col gap-4 lg:flex-row">
    <div class="relative h-64 flex-1 overflow-hidden rounded-md border border-[var(--el-border-color-light)] bg-[var(--el-fill-color-light)]">
      <svg class="h-full w-full" viewBox="0 0 400 300" preserveAspectRatio="xMidYMid slice" role="img" aria-label="涟漪水面演示">
        <defs>
          <filter id="gdn-ripple" x="-10%" y="-10%" width="120%" height="120%">
            <!-- type=turbulence 的噪声比 fractalNoise 更圆润, 更像水波 -->
            <feTurbulence type="turbulence" :baseFrequency="`${state.fx.toFixed(4)} ${state.fy.toFixed(4)}`" numOctaves="2" seed="7" result="noise">
              <!-- SMIL <animate>: 浏览器原生动画, 无需任何 JS -->
              <animate
                attributeName="baseFrequency"
                :values="waveValues"
                :dur="`${state.dur}s`"
                repeatCount="indefinite"
              />
            </feTurbulence>
            <feDisplacementMap in="SourceGraphic" in2="noise" :scale="state.scale" xChannelSelector="R" yChannelSelector="G" />
          </filter>
        </defs>
        <image :href="mainPhoto" x="0" y="0" width="400" height="300" preserveAspectRatio="xMidYMid slice" filter="url(#gdn-ripple)" />
      </svg>
      <span class="pointer-events-none absolute bottom-2 left-3 text-xs text-[var(--el-text-color-secondary)]">水面荡漾 · SVG 原生 SMIL 动画, 零 JS</span>
    </div>

    <!-- 控制面板 -->
    <div class="w-full shrink-0 space-y-1 lg:w-56">
      <div v-for="c in controls" :key="c.key" class="flex items-center gap-2">
        <span class="w-14 shrink-0 text-xs text-[var(--el-text-color-secondary)]">{{ c.label }}</span>
        <el-slider v-model="state[c.key]" :min="c.min" :max="c.max" :step="c.step ?? 1" size="small" class="flex-1" />
      </div>
      <p class="pt-1 text-xs leading-5 text-[var(--el-text-color-secondary)]">
        基频(baseFrequency)决定波纹的疏密: 横向频率低、纵向频率高, 波就被"拉长"成水面;
        animate 标签让基频往复变化, 位移场随时间流动, 静态滤镜就动了起来。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
// SVG 滤镜涟漪(garden.bradwoods.io/notes/svg/filters):
// feTurbulence 生成噪声场, feDisplacementMap 按噪声的 R/G 通道扭曲源图像的 x/y 坐标
import { mainPhoto } from './texture'

/** 滑杆配置 */
interface SliderConf {
  key: 'fx' | 'fy' | 'scale' | 'dur'
  label: string
  min: number
  max: number
  step?: number
}

/** 控制项 */
const controls: SliderConf[] = [
  { key: 'fx', label: '横向密', min: 0.004, max: 0.02, step: 0.001 },
  { key: 'fy', label: '纵向密', min: 0.02, max: 0.09, step: 0.001 },
  { key: 'scale', label: '波幅', min: 6, max: 60 },
  { key: 'dur', label: '周期s', min: 2, max: 10, step: 0.5 },
]

/** 可调参数 */
const state = reactive<Record<string, number>>({ fx: 0.01, fy: 0.05, scale: 24, dur: 5 })

/** SMIL 动画值: 基频在两档间往复, 形成荡漾 */
const waveValues = computed(
  () => `${state.fx.toFixed(4)} ${state.fy.toFixed(4)};${(state.fx * 1.5).toFixed(4)} ${(state.fy * 0.6).toFixed(4)};${state.fx.toFixed(4)} ${state.fy.toFixed(4)}`,
)
</script>
