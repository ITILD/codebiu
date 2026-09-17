<template>
  <!-- 页面级落叶: 自右上悬枝梢腹一带现身, 分段缓动飘落, 至池塘水面渐隐消失;
       轨道高度铺满页面根, 终点按池塘实测位置回写 --fall-to
       (prefers-reduced-motion 关闭) -->
  <div ref="rootEl" class="falling-leaves pointer-events-none absolute inset-0 z-[1] overflow-hidden" aria-hidden="true">
    <span
      v-for="(f, i) in fallers"
      :key="`f${i}`"
      class="leaf-fall absolute h-full w-0 [will-change:transform,opacity]"
      :style="{
        left: `${f.left}%`,
        top: `${f.top}%`,
        '--fall-to': `${f.fallTo}%`,
        animationDuration: `${f.duration}s`,
        animationDelay: `${f.delay}s`,
      }"
    >
      <i class="absolute inset-0">
        <!-- 叶形与水墨生长枝(Canvas)的叶一致: 两段贝塞尔尖椭圆, 两端收尖(竹叶), 无叶脉 -->
        <svg
          viewBox="0 0 16 16"
          class="leaf-spin absolute top-0 left-0"
          :style="{ width: `${f.size}px`, height: `${f.size}px`, marginLeft: `${-f.size / 2}px`, color: f.color, animationDuration: `${f.spin}s` }"
        >
          <path d="M1 8 Q7.3 5.5 15 8 Q7.3 10.5 1 8 Z" fill="currentColor" opacity="0.55" />
        </svg>
      </i>
    </span>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

// 落叶参数每次刷新随机; 轨道锚在悬枝梢腹一带(页高 6%~15%),
// 坠落终点由池塘顶缘实测回写 —— 100% 处恰为水面
const rootEl = ref<HTMLElement | null>(null)

function mulberry32(seed: number) {
  return () => {
    seed |= 0
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}
const rand = mulberry32((Math.random() * 0x7fffffff) | 0)

/** 叶色限定在苔绿色板内, 与全站主题一致 */
const LEAF_COLORS = ['var(--note-green)', 'var(--note-accent)', 'var(--note-green-deep)']
const pickColor = () => LEAF_COLORS[Math.floor(rand() * LEAF_COLORS.length)]

/** 落叶数量 */
const props = withDefaults(defineProps<{ falling?: number }>(), { falling: 5 })

interface Faller {
  left: number; top: number; size: number; duration: number; delay: number; spin: number
  color: string; fallTo: number
}

const fallers = ref<Faller[]>(Array.from({ length: props.falling }, () => ({
  left: 58 + rand() * 36,
  top: 6 + rand() * 9, // 自悬枝梢腹现身
  size: 18 + rand() * 10,
  duration: 13 + rand() * 7,
  delay: -rand() * 24, // 负延迟: 页面打开即处于飘落中途, 不齐步
  spin: 7 + rand() * 6,
  color: pickColor(),
  fallTo: 74, // 占位, 挂载后按池塘位置修正
})))

/** 实测池塘顶缘占页高百分比, 修正每片叶的坠落终点 */
function measure() {
  const root = rootEl.value
  if (!root) return
  const rootRect = root.getBoundingClientRect()
  const h = rootRect.height || 1
  const pond = document.querySelector('.pond-stage')
  const pondPct = pond
    ? ((pond.getBoundingClientRect().top - rootRect.top) / h) * 100
    : 82
  for (const f of fallers.value) {
    const target = Math.max(30, pondPct + 1.5 - f.top)
    if (Math.abs(target - f.fallTo) > 2) {
      f.fallTo = +target.toFixed(1) // 变化过小不重设, 避免动画中途跳变
    }
  }
}

let ro: ResizeObserver | null = null

onMounted(() => {
  measure()
  if ('ResizeObserver' in window) {
    ro = new ResizeObserver(measure)
    ro.observe(document.body)
  }
})

onBeforeUnmount(() => ro?.disconnect())
</script>

<style scoped>
/* 落叶轨道: 静态定位/尺寸已转 uno 原子类; 每段 keyframe 自带 ease-in-out,
   形成缓降—摆动—再缓降的呼吸节奏(动画声明依赖 JS 注入的 --fall-to/duration, 保留在 style) */
.leaf-fall {
  animation-name: leaf-fall;
  animation-timing-function: ease-in-out;
  animation-iteration-count: infinite;
}

/* 飘落: 各段横移错开成 S 形轨迹; 末端缩小渐隐(远去 + 沉入水面) */
@keyframes leaf-fall {
  0% {
    transform: translate3d(0, -3%, 0) scale(1);
    opacity: 0;
  }
  6% {
    opacity: 0.72;
  }
  24% {
    transform: translate3d(-18px, calc(var(--fall-to) * 0.24), 0);
  }
  48% {
    transform: translate3d(15px, calc(var(--fall-to) * 0.48), 0);
  }
  72% {
    transform: translate3d(-14px, calc(var(--fall-to) * 0.72), 0);
  }
  86% {
    opacity: 0.55;
  }
  100% {
    transform: translate3d(9px, var(--fall-to), 0) scale(0.82);
    opacity: 0;
  }
}

/* 叶体自身旋转, 与轨道解耦(动画声明保留, 静态定位已转 uno) */
.leaf-spin {
  animation-name: leaf-spin;
  animation-timing-function: linear;
  animation-iteration-count: infinite;
}

@keyframes leaf-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .leaf-fall,
  .leaf-spin {
    animation: none;
  }
  .leaf-fall {
    display: none;
  }
}
</style>
