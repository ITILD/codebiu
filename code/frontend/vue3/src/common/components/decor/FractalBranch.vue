<template>
  <!-- 分形悬枝: 递归(分形)生成的 SVG 枝条与叶簇, 自纸页右上角垂落;
       SMIL 轻风摇摆 + 数片落叶(均可用 prefers-reduced-motion 关闭) -->
  <div class="fractal-branch pointer-events-none absolute inset-0 z-[1] overflow-hidden" aria-hidden="true">
    <!-- 悬枝本体: 外层 g 负责定位, 内层 g 绕枝基(0,0)摇摆 -->
    <svg class="absolute -top-1 right-0 w-36 sm:w-44 md:w-56" viewBox="0 0 240 270" fill="none">
      <g transform="translate(228 -8) rotate(-150)">
        <g>
          <animateTransform
            v-if="!reducedMotion"
            attributeName="transform"
            type="rotate"
            values="-1.6 0 0; 1.3 0 0; -1.6 0 0"
            keyTimes="0; 0.5; 1"
            calcMode="spline"
            keySplines="0.45 0 0.55 1; 0.45 0 0.55 1"
            dur="8.5s"
            repeatCount="indefinite"
          />
          <!-- 枝条: 末梢细淡、枝基粗实 -->
          <path
            v-for="(s, i) in segments"
            :key="`s${i}`"
            :d="`M${s.x1.toFixed(1)} ${s.y1.toFixed(1)} L${s.x2.toFixed(1)} ${s.y2.toFixed(1)}`"
            :stroke-width="s.width.toFixed(2)"
            :stroke-opacity="s.opacity.toFixed(2)"
            stroke="var(--note-green-deep)"
            stroke-linecap="round"
          />
          <!-- 叶簇: 杏仁状小叶 + 浅色叶脉 -->
          <g
            v-for="(l, i) in leaves"
            :key="`l${i}`"
            :transform="`translate(${l.x.toFixed(1)} ${l.y.toFixed(1)}) rotate(${l.angle.toFixed(1)}) scale(${l.size.toFixed(2)})`"
          >
            <path d="M0 0 C 5 -5 7 -11 0 -16 C -7 -11 -5 -5 0 0 Z" :fill="l.color" :fill-opacity="l.opacity.toFixed(2)" />
            <path d="M0 -1.5 V-14" stroke="var(--note-paper)" stroke-width="0.7" :stroke-opacity="(l.opacity * 0.8).toFixed(2)" />
          </g>
        </g>
      </g>
    </svg>

    <!-- 落叶: 外层轨道负责纵向飘落与横移, 叶体自身旋转 -->
    <span
      v-for="(f, i) in fallers"
      :key="`f${i}`"
      class="leaf-fall"
      :style="{ left: `${f.left}%`, animationDuration: `${f.duration}s`, animationDelay: `${f.delay}s` }"
    >
      <i class="leaf-body">
        <svg
          viewBox="0 0 16 16"
          class="leaf-spin"
          :style="{ width: `${f.size}px`, height: `${f.size}px`, marginLeft: `${-f.size / 2}px`, color: f.color, animationDuration: `${f.spin}s` }"
        >
          <path d="M8 2 C 12 6 12 11 8 14 C 4 11 4 6 8 2 Z" fill="currentColor" opacity="0.85" />
          <path d="M8 3 V13" stroke="var(--note-paper)" stroke-width="0.8" opacity="0.7" />
        </svg>
      </i>
    </span>
  </div>
</template>

<script setup lang="ts">
// 分形树思路: 每根枝条末端递归分生两根子枝(角度张开、长度递减),
// 末梢节点生叶 —— 少量规则即可生成自然形态的枝叶(零图片依赖)
import { onMounted } from 'vue'

/** 落叶数量 */
const props = withDefaults(defineProps<{ falling?: number }>(), { falling: 4 })

/** 用户开启"减少动态效果"时, 不渲染 SMIL/CSS 动画 */
const reducedMotion = ref(false)
onMounted(() => {
  reducedMotion.value = window.matchMedia('(prefers-reduced-motion: reduce)').matches
})

/** 确定性伪随机: 固定种子保证每次渲染形态一致 */
function mulberry32(seed: number) {
  return () => {
    seed |= 0
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

interface Segment {
  x1: number; y1: number; x2: number; y2: number
  width: number; opacity: number
}
interface Leaf {
  x: number; y: number; angle: number; size: number
  color: string; opacity: number
}
interface Faller {
  left: number; size: number; duration: number; delay: number; spin: number
  color: string
}

const rand = mulberry32(20240910)
/** 叶色限定在苔绿色板内, 与全站主题一致 */
const LEAF_COLORS = ['var(--note-green)', 'var(--note-accent)', 'var(--note-green-deep)']
const pickColor = () => LEAF_COLORS[Math.floor(rand() * LEAF_COLORS.length)]

const MAX_DEPTH = 6
const segments: Segment[] = []
const leaves: Leaf[] = []

/** 递归分生枝条; angle 为弧度, -PI/2 表示向上 */
function grow(x: number, y: number, angle: number, len: number, width: number, depth: number) {
  const x2 = x + Math.cos(angle) * len
  const y2 = y + Math.sin(angle) * len
  segments.push({ x1: x, y1: y, x2, y2, width, opacity: 0.26 + (depth / MAX_DEPTH) * 0.3 })

  // 末梢生叶(朝向与枝条一致)
  if (depth <= 0) {
    leaves.push({
      x: x2, y: y2,
      angle: (angle * 180) / Math.PI + 90,
      size: 0.55 + rand() * 0.5,
      color: pickColor(),
      opacity: 0.6 + rand() * 0.25,
    })
    return
  }

  // 浅枝节处偶生小叶, 增加层次
  if (depth <= 3 && rand() < 0.45) {
    leaves.push({
      x: x2, y: y2,
      angle: rand() * 360,
      size: 0.38 + rand() * 0.32,
      color: pickColor(),
      opacity: 0.5 + rand() * 0.25,
    })
  }

  const spread = 0.32 + rand() * 0.2
  const jitter = () => (rand() - 0.5) * 0.14
  grow(x2, y2, angle - spread + jitter(), len * (0.72 + rand() * 0.08), width * 0.72, depth - 1)
  grow(x2, y2, angle + spread + jitter(), len * (0.72 + rand() * 0.08), width * 0.72, depth - 1)
}

grow(0, 0, -Math.PI / 2, 36, 3.4, MAX_DEPTH)

/** 落叶轨道参数(集中在右侧枝冠区域下落) */
const fallers: Faller[] = Array.from({ length: props.falling }, () => ({
  left: 56 + rand() * 38,
  size: 11 + rand() * 7,
  duration: 13 + rand() * 6,
  delay: -rand() * 19,
  spin: 7 + rand() * 6,
  color: pickColor(),
}))
</script>

<style scoped>
/* 落叶轨道: 高度铺满父容器, 位移百分比即相对 Hero 高度 */
.leaf-fall {
  position: absolute;
  top: 0;
  height: 100%;
  width: 0;
  animation-name: note-leaf-fall;
  animation-timing-function: linear;
  animation-iteration-count: infinite;
}

.leaf-body {
  position: absolute;
  inset: 0;
}

/* 飘落: 缓降 + 左右横移 + 淡入淡出 */
@keyframes note-leaf-fall {
  0%   { transform: translate3d(0, -6%, 0); opacity: 0; }
  8%   { opacity: 0.7; }
  25%  { transform: translate3d(-14px, 26%, 0); }
  50%  { transform: translate3d(10px, 55%, 0); }
  75%  { transform: translate3d(-12px, 83%, 0); }
  88%  { opacity: 0.55; }
  100% { transform: translate3d(6px, 108%, 0); opacity: 0; }
}

/* 叶体自身旋转, 与轨道解耦 */
.leaf-spin {
  position: absolute;
  top: 0;
  left: 0;
  animation-name: note-leaf-spin;
  animation-timing-function: linear;
  animation-iteration-count: infinite;
}

@keyframes note-leaf-spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
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
