<template>
  <!-- 页面级落叶: 自右上枝冠区域飘落, 贯穿整页直至页尾池塘水面渐隐;
       纵向飘落轨道 + 横移摆动, 叶体自身旋转(可用 prefers-reduced-motion 关闭) -->
  <div class="falling-leaves pointer-events-none absolute inset-0 z-[1] overflow-hidden" aria-hidden="true">
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
// 落叶参数每次刷新随机; 轨道高度铺满页面根容器,
// 位移百分比即相对整页高度 —— 100% 处恰为页尾池塘水面
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
  left: number; size: number; duration: number; delay: number; spin: number
  color: string
}

/** 落叶轨道参数(集中在右上枝冠区域生成) */
const fallers: Faller[] = Array.from({ length: props.falling }, () => ({
  left: 58 + rand() * 36,
  size: 11 + rand() * 7,
  duration: 14 + rand() * 8,
  delay: -rand() * 20,
  spin: 7 + rand() * 6,
  color: pickColor(),
}))
</script>

<style scoped>
/* 落叶轨道: 高度铺满父容器(页面根), 位移百分比即相对整页高度 */
.leaf-fall {
  position: absolute;
  top: 0;
  height: 100%;
  width: 0;
  animation-name: leaf-fall;
  animation-timing-function: linear;
  animation-iteration-count: infinite;
}

.leaf-body {
  position: absolute;
  inset: 0;
}

/* 飘落: 缓降 + 左右摆动 + 末端沉入水面渐隐 */
@keyframes leaf-fall {
  0%   { transform: translate3d(0, -4%, 0); opacity: 0; }
  6%   { opacity: 0.75; }
  22%  { transform: translate3d(-18px, 24%, 0); }
  46%  { transform: translate3d(14px, 52%, 0); }
  70%  { transform: translate3d(-16px, 78%, 0); }
  88%  { opacity: 0.55; }
  100% { transform: translate3d(10px, 103%, 0); opacity: 0; }
}

/* 叶体自身旋转, 与轨道解耦 */
.leaf-spin {
  position: absolute;
  top: 0;
  left: 0;
  animation-name: leaf-spin;
  animation-timing-function: linear;
  animation-iteration-count: infinite;
}

@keyframes leaf-spin {
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
