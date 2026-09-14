<template>
  <!-- 分形悬枝: 每次进入以随机种子生成形态, rAF 驱动缓慢随机生长(总长预算耗尽即止);
       末梢叶簇随枝条长成渐次舒展, 生长完成后转入 SMIL 轻风摇摆
       (均可用 prefers-reduced-motion 关闭) -->
  <div class="fractal-branch pointer-events-none absolute inset-0 z-[1] overflow-hidden" aria-hidden="true">
    <!-- 悬枝本体: 外层 g 负责定位, 内层 g 绕枝基(0,0)摇摆 -->
    <svg class="absolute -top-1 right-0 w-40 sm:w-52 md:w-64" viewBox="0 0 240 270" fill="none">
      <g transform="translate(228 -8) rotate(-150)">
        <g>
          <animateTransform
            v-if="!reducedMotion && settled"
            attributeName="transform"
            type="rotate"
            values="-1.6 0 0; 1.3 0 0; -1.6 0 0"
            keyTimes="0; 0.5; 1"
            calcMode="spline"
            keySplines="0.45 0 0.55 1; 0.45 0 0.55 1"
            dur="8.5s"
            repeatCount="indefinite"
          />
          <!-- 枝条: 末梢细淡、枝基粗实; 生长中的段按进度截断绘制 -->
          <path
            v-for="(s, i) in segViews"
            :key="`s${i}`"
            :d="s.d"
            :stroke-width="s.width"
            :stroke-opacity="s.opacity"
            stroke="var(--note-green-deep)"
            stroke-linecap="round"
          />
          <!-- 叶簇: 内层 g 用 CSS transform 舒展(与定位用的属性 transform 解耦) -->
          <g
            v-for="(l, i) in leaves"
            :key="`l${i}`"
            :transform="`translate(${l.x.toFixed(1)} ${l.y.toFixed(1)}) rotate(${l.angle.toFixed(1)}) scale(${l.size.toFixed(2)})`"
          >
            <g class="leaf" :class="{ 'leaf-in': grown >= l.born }">
              <path d="M0 0 C 5 -5 7 -11 0 -16 C -7 -11 -5 -5 0 0 Z" :fill="l.color" :fill-opacity="l.opacity.toFixed(2)" />
              <path d="M0 -1.5 V-14" stroke="var(--note-paper)" stroke-width="0.7" :stroke-opacity="(l.opacity * 0.8).toFixed(2)" />
            </g>
          </g>
        </g>
      </g>
    </svg>
  </div>
</template>

<script setup lang="ts">
// 分形树思路: 每根枝条末端随机分生两(偶发三)根子枝, 角度张开、长度递减;
// 生长节奏 = 每段耗时随段长随机, 子枝在母枝长成后才抽芽, 末梢节点生叶
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

/** 用户开启"减少动态效果"时, 跳过生长动画直接呈现完成形态 */
const reducedMotion = ref(false)
/** 生长是否完成(完成后才启用摇摆) */
const settled = ref(false)

/** 确定性伪随机: 种子取自 Math.random, 每次刷新形态随机 */
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

interface Segment {
  x1: number; y1: number; x2: number; y2: number
  width: number; opacity: number
  start: number; dur: number
}
interface Leaf {
  x: number; y: number; angle: number; size: number
  color: string; opacity: number
  born: number
}

// ---- 形态参数(魔法值收敛为常量) ----
const MAX_DEPTH = 7          // 侧枝递归深度上限
const LENGTH_BUDGET = 780 + rand() * 280 // 总长预算: 耗尽即停止分生(随机 780~1060)
const START_LEN = 44 + rand() * 8      // 主干首段长度
const START_WIDTH = 3.6                // 枝基线宽
const GROW_SPEED = 0.03                // 每像素生长耗时(秒)
/** 重力方向(局部坐标): 枝基经 rotate(-150) 定位后, -PI/2 映射为屏幕左下 */
const GRAVITY = -Math.PI / 2
/** 枝条绝对朝向夹角(局部坐标): 将树冠收束在可视区内且不过分横向铺开 */
const ANGLE_MIN = -2.2
const ANGLE_MAX = -0.45
/** 主干段数: 前 1~2 段不分叉, 走满即分出主树杈 */
const TRUNK_SEGS = 1 + (rand() < 0.5 ? 1 : 0)

const segments: Segment[] = []
const leaves: Leaf[] = []
let budget = LENGTH_BUDGET

/** 向重力方向轻拉并收束到夹角区间(垂柳式弯垂, 防横向逸出) */
function bend(a: number, droop: number) {
  let d = a - GRAVITY
  if (d > Math.PI) d -= 2 * Math.PI
  if (d < -Math.PI) d += 2 * Math.PI
  return Math.min(ANGLE_MAX, Math.max(ANGLE_MIN, a - d * droop))
}

/** 递归分生枝条; angle 为弧度, -PI/2 表示向上; start 为该段开始生长的时刻(秒);
 *  trunk 为剩余主干段数(主干不分叉, 走满后一次分出主树杈) */
function grow(x: number, y: number, angle: number, len: number, width: number, depth: number, start: number, trunk = TRUNK_SEGS) {
  if (budget <= 0) return
  budget -= len

  const x2 = x + Math.cos(angle) * len
  const y2 = y + Math.sin(angle) * len
  const dur = len * GROW_SPEED * (0.8 + rand() * 0.5)
  const end = start + dur
  segments.push({ x1: x, y1: y, x2, y2, width, opacity: 0.26 + (depth / MAX_DEPTH) * 0.3, start, dur })

  const addLeaf = (born: number, angleJitter = true, sizeMin = 0.4) => {
    leaves.push({
      x: x2, y: y2,
      angle: angleJitter ? rand() * 360 : (angle * 180) / Math.PI + 90,
      size: sizeMin + rand() * 0.5,
      color: pickColor(),
      opacity: 0.5 + rand() * 0.35,
      born,
    })
  }

  // ---- 主干: 沿途零星小叶, 走满后一次分出 2~3 根粗壮主树杈 ----
  if (trunk > 0) {
    if (rand() < 0.35) addLeaf(end, true, 0.28)
    if (trunk > 1) {
      grow(x2, y2, angle + (rand() - 0.5) * 0.16, len * (0.9 + rand() * 0.12), width * 0.92, depth, end, trunk - 1)
      return
    }
    const n = 2 + (rand() < 0.55 ? 1 : 0)
    const base = angle + (rand() - 0.5) * 0.1
    const spread = 0.4 + rand() * 0.25
    for (let i = 0; i < n; i++) {
      grow(
        x2, y2,
        bend(base + (i - (n - 1) / 2) * spread + (rand() - 0.5) * 0.12, 0.08),
        len * (0.6 + rand() * 0.14), width * 0.8, depth - 1, end + rand() * 0.2, 0
      )
    }
    // 中央领导枝继续抽长, 保持主势
    if (rand() < 0.7) {
      grow(x2, y2, bend(base, 0.1), len * (0.5 + rand() * 0.1), width * 0.6, depth - 1, end, 0)
    }
    return
  }

  // ---- 侧枝: 末梢收笔; 沿途各节均可能出叶(近根稀疏小巧, 越往外越密) ----
  if (depth <= 0 || budget <= 0) {
    addLeaf(end, false)
    return
  }
  const nearRoot = depth >= MAX_DEPTH - 2
  if (rand() < (nearRoot ? 0.3 : depth <= 3 ? 0.55 : 0.42)) {
    addLeaf(end, true, nearRoot ? 0.28 : 0.4)
  }

  // 不对称张角: 两子枝开合程度随机错开, 分型更自然; 越到末梢越下垂
  const spread = 0.34 + rand() * 0.26
  const asym = 0.55 + rand() * 0.9
  const droop = 0.06 + (1 - depth / MAX_DEPTH) * 0.12
  const shrink = () => len * (0.74 + rand() * 0.12)
  const childStart = end + rand() * 0.2
  grow(x2, y2, bend(angle - spread * asym, droop), shrink(), width * 0.72, depth - 1, childStart)
  grow(x2, y2, bend(angle + spread * (2 - asym), droop), shrink(), width * 0.72, depth - 1, childStart)
}

grow(0, 0, -Math.PI / 2, START_LEN, START_WIDTH, MAX_DEPTH, 0.15)

/** 全树长成所需总时长(叶簇再留 0.4s 舒展) */
const totalTime = segments.reduce((m, s) => Math.max(m, s.start + s.dur), 0) + 0.4

// ---- 生长驱动: rAF 逐帧推进 grown(秒), 完成后停止 ----
const grown = ref(0)
let raf = 0

function tick(now: number, t0: number) {
  const t = (now - t0) / 1000
  grown.value = Math.min(t, totalTime)
  if (t >= totalTime) {
    settled.value = true
    return
  }
  raf = requestAnimationFrame((n) => tick(n, t0))
}

onMounted(() => {
  reducedMotion.value = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (reducedMotion.value) {
    grown.value = totalTime
    settled.value = true
    return
  }
  raf = requestAnimationFrame((n) => tick(n, performance.now()))
})

onBeforeUnmount(() => cancelAnimationFrame(raf))

/** 按生长进度截断各段: 末段用缓出曲线, 梢部渐缓更自然 */
const segViews = computed(() => {
  const out: { d: string; width: string; opacity: string }[] = []
  for (const s of segments) {
    const raw = (grown.value - s.start) / s.dur
    if (raw <= 0) continue
    const p = raw >= 1 ? 1 : 1 - (1 - raw) * (1 - raw)
    const x2 = s.x1 + (s.x2 - s.x1) * p
    const y2 = s.y1 + (s.y2 - s.y1) * p
    out.push({
      d: `M${s.x1.toFixed(1)} ${s.y1.toFixed(1)} L${x2.toFixed(1)} ${y2.toFixed(1)}`,
      width: s.width.toFixed(2),
      opacity: s.opacity.toFixed(2),
    })
  }
  return out
})
</script>

<style scoped>
/* 叶簇舒展: 从叶柄处放大淡入(内层 g 与定位 transform 解耦后由 CSS 驱动) */
.leaf {
  transform-box: fill-box;
  transform-origin: 50% 100%;
  transform: scale(0);
  opacity: 0;
  transition: transform 0.9s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.9s ease;
}

.leaf-in {
  transform: scale(1);
  opacity: 1;
}
</style>
