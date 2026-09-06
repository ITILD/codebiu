<template>
  <!-- 彩色聚光: saturation 混合的黑色遮罩把圈外区域变灰, 圈内保留色彩 -->
  <div class="flex flex-col gap-4 lg:flex-row lg:items-center">
    <div
      ref="box"
      class="relative isolate min-h-52 flex-1 cursor-crosshair overflow-hidden rounded-md border border-[var(--el-border-color-light)]"
      @mousemove="onMove"
    >
      <img :src="src" alt="彩色聚光演示图" loading="lazy" decoding="async" class="block w-full">
      <!-- 黑色 = 饱和度 0; saturation 混合把黑色覆盖处变灰, 透明圆孔处保留原色 -->
      <div
        class="pointer-events-none absolute inset-0"
        :style="{
          background: `radial-gradient(circle ${radius}px at ${x}% ${y}%, hsla(0, 0%, 0%, 0) 0 55%, hsla(0, 0%, 0%, 1) 100%)`,
          mixBlendMode: 'saturation',
        }"
      />
    </div>

    <!-- 控制面板 -->
    <div class="w-full shrink-0 space-y-3 lg:w-56">
      <div class="flex items-center gap-2">
        <span class="w-16 shrink-0 text-xs text-[var(--el-text-color-secondary)]">光圈半径</span>
        <el-slider v-model="radius" :min="60" :max="400" size="small" class="flex-1" />
      </div>
      <p class="text-xs leading-5 text-[var(--el-text-color-secondary)]">
        移动鼠标: mix-blend-mode: saturation 取顶层的"饱和度"、底层的"色相与明度"。黑色饱和度为 0，覆盖处即被去色。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
// 彩色聚光(garden.bradwoods.io/notes/css/blend-modes#colored-area):
// 黑色径向渐变 + mix-blend-mode: saturation, 圆孔内保留彩色、圈外灰度
import { mainPhoto } from './texture'

/** 可传入自定义底图 */
withDefaults(defineProps<{ src?: string }>(), { src: () => mainPhoto })

/** 聚光中心 x(百分比) */
const x = ref(50)

/** 聚光中心 y(百分比) */
const y = ref(50)

/** 光圈半径(px) */
const radius = ref(150)

/** 容器引用 */
const box = ref<HTMLElement | null>(null)

/** 鼠标移动: 更新聚光中心 */
function onMove(e: MouseEvent) {
  const r = box.value?.getBoundingClientRect()
  if (!r) return
  x.value = ((e.clientX - r.left) / r.width) * 100
  y.value = ((e.clientY - r.top) / r.height) * 100
}
</script>
