<template>
  <!-- 半调网点: 点阵层 + hard-light 图像层, 父级 contrast 强化网点 -->
  <div class="flex flex-col gap-4 lg:flex-row">
    <div class="flex-1 overflow-hidden rounded-md border border-[var(--el-border-color-light)]">
      <!-- isolate 困住混合; contrast 把柔和渐变压成硬边网点 -->
      <div class="relative isolate aspect-[4/3] w-full overflow-hidden" :style="{ filter: `contrast(${state.contrast}%)` }">
        <!-- 网点层: 径向渐变平铺 + 旋转 -->
        <div
          class="absolute -inset-1/2"
          :style="{
            transform: `rotate(${state.angle}deg)`,
            background: `radial-gradient(circle at center, ${dotColor} 0 54%, hsl(0, 0%, 100%) 55%)`,
            backgroundSize: `${state.dot}px ${state.dot}px`,
          }"
        />
        <!-- 图像层: 灰度后以 hard-light 压到点阵上 -->
        <img
          :src="src"
          alt="半调网点演示图"
          loading="lazy"
          decoding="async"
          class="absolute inset-0 h-full w-full object-cover"
          :style="{ filter: `grayscale(1) brightness(${state.brightness}%) contrast(100%)`, mixBlendMode: 'hard-light' }"
        >
      </div>
    </div>

    <!-- 控制面板 -->
    <div class="w-full shrink-0 space-y-1 lg:w-56">
      <div v-for="c in controls" :key="c.key" class="flex items-center gap-2">
        <span class="w-16 shrink-0 text-xs text-[var(--el-text-color-secondary)]">{{ c.label }}</span>
        <el-slider v-model="state[c.key]" :min="c.min" :max="c.max" :step="c.step ?? 1" size="small" class="flex-1" />
      </div>
      <div class="flex items-center gap-2 pt-1">
        <span class="w-16 shrink-0 text-xs text-[var(--el-text-color-secondary)]">网点色</span>
        <el-color-picker v-model="dotColor" size="small" />
      </div>
      <p class="text-xs leading-5 text-[var(--el-text-color-secondary)]">
        印刷术的半调(halftone): 用同色网点的大小疏密表现明暗，hard-light 带来强烈对比。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
// 半调网点(garden.bradwoods.io/notes/css/blend-modes#halftone):
// radial-gradient 点阵 + mix-blend-mode: hard-light 图像 + 父级 filter: contrast 放大
import { mainPhoto } from './texture'

/** 可传入自定义底图 */
withDefaults(defineProps<{ src?: string }>(), { src: () => mainPhoto })

/** 滑杆配置 */
interface SliderConf {
  key: 'dot' | 'brightness' | 'contrast' | 'angle'
  label: string
  min: number
  max: number
  step?: number
}

/** 控制项 */
const controls: SliderConf[] = [
  { key: 'dot', label: '网点大小', min: 2, max: 14, step: 0.5 },
  { key: 'brightness', label: '图像亮度', min: 30, max: 130 },
  { key: 'contrast', label: '网点对比', min: 400, max: 3000, step: 100 },
  { key: 'angle', label: '网点角度', min: 0, max: 90 },
]

/** 可调参数集合(默认值取自原笔记) */
const state = reactive<Record<string, number>>({
  dot: 6, brightness: 70, contrast: 1800, angle: 20,
})

/** 网点颜色 */
const dotColor = ref('#1c2b1c')
</script>
