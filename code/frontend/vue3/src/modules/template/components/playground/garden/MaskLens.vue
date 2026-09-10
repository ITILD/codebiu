<template>
  <!-- 彩色放大镜: 灰度底图之上, mask 径向渐变挖出圆孔透出彩色层, 孔随鼠标移动 -->
  <div class="flex flex-col gap-4 lg:flex-row">
    <div
      ref="stage"
      class="lens-stage relative h-64 flex-1 cursor-none overflow-hidden rounded-md border border-[var(--el-border-color-light)] bg-[var(--el-fill-color-light)]"
      @mousemove="onMove"
      @mouseleave="hide"
    >
      <!-- 底层: 去色图 -->
      <img :src="mainPhoto" alt="灰度底图" loading="lazy" decoding="async" class="absolute inset-0 h-full w-full object-cover grayscale" />
      <!-- 顶层: 彩色图, 用 mask 只露出圆形区域 -->
      <img
        :src="mainPhoto"
        alt="彩色透镜"
        loading="lazy"
        decoding="async"
        class="absolute inset-0 h-full w-full object-cover"
        :style="lensStyle"
        :class="{ 'opacity-0': !inside }"
      />
      <!-- 透镜圆环装饰 -->
      <span
        class="pointer-events-none absolute rounded-full border-2 border-white/80 shadow-[0_0_18px_rgba(0,0,0,0.35)] transition-opacity"
        :class="{ 'opacity-0': !inside }"
        :style="ringStyle"
      />
      <span class="pointer-events-none absolute bottom-2 left-3 text-xs text-[var(--el-text-color-secondary)]">移动鼠标 · 彩色透镜跟随</span>
    </div>

    <!-- 控制面板 -->
    <div class="w-full shrink-0 space-y-1 lg:w-56">
      <div class="flex items-center gap-2">
        <span class="w-14 shrink-0 text-xs text-[var(--el-text-color-secondary)]">镜径</span>
        <el-slider v-model="state.radius" :min="40" :max="140" size="small" class="flex-1" />
      </div>
      <p class="pt-1 text-xs leading-5 text-[var(--el-text-color-secondary)]">
        mask-image: radial-gradient 在顶层图上挖一个"只有圆内不透明"的遮罩, 圆心跟随鼠标;
        底层是 grayscale(1) 的同图, 于是圆孔内是彩色、圆外是黑白 —— 不需要任何裁剪或第二份资源。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
// CSS mask 聚焦镜(garden.bradwoods.io/notes/svg/mask):
// mask-image 渐变的 alpha 通道决定显隐, 径向渐变即圆形透镜
import type { CSSProperties } from 'vue'
import { mainPhoto } from './texture'

/** 透镜半径(px) */
const state = reactive({ radius: 80 })

/** 鼠标相对舞台坐标 */
const pos = reactive({ x: -999, y: -999 })

/** 是否在舞台内(控制透镜显隐) */
const inside = ref(false)

/** 舞台元素引用 */
const stage = ref<HTMLElement | null>(null)

/** 顶层彩色图的 mask 样式 */
const lensStyle = computed<CSSProperties>(() => {
  const g = `radial-gradient(circle ${state.radius}px at ${pos.x}px ${pos.y}px, #000 ${state.radius - 2}px, transparent ${state.radius}px)`
  return { maskImage: g, WebkitMaskImage: g }
})

/** 圆环装饰的位置样式 */
const ringStyle = computed<CSSProperties>(() => ({
  left: `${pos.x - state.radius}px`,
  top: `${pos.y - state.radius}px`,
  width: `${state.radius * 2}px`,
  height: `${state.radius * 2}px`,
}))

/** 鼠标移动: 更新透镜圆心 */
function onMove(e: MouseEvent) {
  const r = stage.value?.getBoundingClientRect()
  if (!r) return
  pos.x = e.clientX - r.left
  pos.y = e.clientY - r.top
  inside.value = true
}

/** 离开舞台: 隐藏透镜 */
function hide() {
  inside.value = false
}
</script>
