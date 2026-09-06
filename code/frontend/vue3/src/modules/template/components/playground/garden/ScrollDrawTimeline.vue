<template>
  <!-- 滚动描线时间轴: SVG clip-path 矩形随滚动下移, 逐渐露出曲线 -->
  <div ref="root" class="relative py-2">
    <div v-for="(it, i) in items" :key="i" data-row class="flex gap-4">
      <!-- 线轴列: 圆点与曲线对齐 -->
      <div class="relative w-20 shrink-0">
        <span
          class="absolute left-1/2 top-1.5 z-10 h-3.5 w-3.5 -translate-x-1/2 rounded-full border-2 transition-all duration-500"
          :class="litCount > i
            ? 'scale-110 border-[var(--el-color-primary)] bg-[var(--el-color-primary)] shadow-[0_0_0_4px_var(--el-color-primary-light-8)]'
            : 'border-[var(--el-border-color)] bg-[var(--el-bg-color-page)]'"
        />
      </div>
      <div class="min-w-0 flex-1 pb-6 last:pb-0">
        <div class="rounded-md border border-[var(--el-border-color-light)] bg-[var(--el-bg-color)] px-4 py-3">
          <div class="text-xs font-semibold text-[var(--el-color-primary)]">{{ it.phase }}</div>
          <div class="mt-1 text-sm leading-6 text-[var(--el-text-color-regular)]">{{ it.text }}</div>
        </div>
      </div>
    </div>

    <!-- 覆盖整列的曲线 SVG: 底线常显, 渐变线被 clip-path 逐渐揭示 -->
    <svg
      ref="svg"
      class="pointer-events-none absolute inset-y-0 left-0 h-full"
      width="80"
      viewBox="0 0 80 100"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="garden-draw-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#7fae6f" />
          <stop offset="50%" stop-color="#4a7c59" />
          <stop offset="100%" stop-color="#b08a3e" />
        </linearGradient>
        <clipPath id="garden-draw-clip">
          <rect ref="clipRect" x="-4" y="0" width="88" height="0" />
        </clipPath>
      </defs>
      <!-- 底线: 浅色完整曲线 -->
      <path :d="PATH" fill="none" stroke="var(--el-border-color)" stroke-width="2" vector-effect="non-scaling-stroke" />
      <!-- 前景线: 渐变色, 被 clip-path 裁剪出"正在绘制"效果 -->
      <path
        :d="PATH"
        fill="none"
        stroke="url(#garden-draw-grad)"
        stroke-width="3"
        stroke-linecap="round"
        vector-effect="non-scaling-stroke"
        clip-path="url(#garden-draw-clip)"
      />
    </svg>
  </div>
</template>

<script setup lang="ts">
// 滚动驱动的描线动画(garden.bradwoods.io/notes/svg/scroll-driven-draw-animation):
// 先整条渲染曲线, 再用 clipPath 矩形只露出已"画过"的部分, 滚动时平移裁剪框
import type { TimelineItem } from './types'

/** 时间轴条目 */
defineProps<{ items: TimelineItem[] }>()

/** S 形曲线路径(viewBox 坐标, preserveAspectRatio=none 拉伸到实际高度) */
const PATH = 'M40 0 V14 C40 26 72 24 72 38 C72 52 8 48 8 62 C8 76 40 74 40 86 V100'

/** 根容器 */
const root = ref<HTMLElement | null>(null)

/** SVG 引用(取实际像素高度) */
const svg = ref<SVGSVGElement | null>(null)

/** 裁剪矩形(直接改 DOM 属性, 避免逐帧重渲染) */
const clipRect = ref<SVGRectElement | null>(null)

/** 已点亮的节点数 */
const litCount = ref(0)

/** 就近查找滚动容器(应用主体内容可能滚动于内部容器) */
function getScroller(el: HTMLElement | null): HTMLElement | null {
  let p = el?.parentElement ?? null
  while (p) {
    const o = getComputedStyle(p).overflowY
    if (o === 'auto' || o === 'scroll') return p
    p = p.parentElement
  }
  return null
}

/** 计算绘制进度并更新裁剪框与节点点亮状态 */
function update() {
  const el = root.value
  const rect = clipRect.value
  const svgEl = svg.value
  if (!el || !rect || !svgEl) return
  const box = el.getBoundingClientRect()
  const vh = window.innerHeight
  // 顶边到达视口 85% 处开始画, 底边到达视口 85% 处画完
  const p = Math.min(1, Math.max(0, (vh * 0.85 - box.top) / box.height))
  const h = p * svgEl.clientHeight
  rect.setAttribute('height', String(h))
  // 曲线经过哪个圆点, 哪个圆点点亮
  let lit = 0
  el.querySelectorAll<HTMLElement>('[data-row]').forEach((row) => {
    if (row.offsetTop + 10 <= h) lit++
  })
  litCount.value = lit
}

/** 滚动句柄(rAF 节流) */
const onScroll = () => requestAnimationFrame(update)

/** 滚动容器与尺寸监听 */
let scroller: HTMLElement | null = null
let ro: ResizeObserver | null = null

onMounted(() => {
  update()
  window.addEventListener('scroll', onScroll, { passive: true })
  scroller = getScroller(root.value)
  scroller?.addEventListener('scroll', onScroll, { passive: true })
  ro = new ResizeObserver(onScroll)
  if (root.value) ro.observe(root.value)
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', onScroll)
  scroller?.removeEventListener('scroll', onScroll)
  ro?.disconnect()
})
</script>
