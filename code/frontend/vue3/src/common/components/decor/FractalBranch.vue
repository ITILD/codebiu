<template>
  <!-- 水墨生长枝: Canvas 2D 双层——静态层增量累积已完成笔画(永不重绘),
       动态层每帧只画"生长中的枝 + 舒展中的叶"后清空; rAF 驱动、dt 钳制,
       生长结束取消 rAF 并清空动态层(常驻开销归零)。
       结构生成为无 DOM 纯函数, 在 inline Blob Worker 中执行(失败回落 requestIdleCallback)。
       容器锚在卡片右上, 宽≈卡片 54%, 高随机 120%~150%, 墨枝垂出卡底;
       IntersectionObserver 进入视口播放一次; prefers-reduced-motion 直接一次成图 -->
  <div
    ref="rootEl"
    class="ink-branch pointer-events-none absolute z-[1] -top-4 -right-2 md:-top-6 md:-right-6 w-[54%]"
    :style="{ height: `${boxH}%` }"
    aria-hidden="true"
  >
    <canvas ref="staticEl" class="absolute inset-0 h-full w-full" />
    <canvas ref="dynamicEl" class="absolute inset-0 h-full w-full" />
  </div>
</template>

<script setup lang="ts">
// 分形规范: 深度≤6, 每枝折线段 11~18px(逐枝随机), 段向重力(90°)收敛 0.045×(0.5+depth×0.35) + 随机扰动;
// 子枝长/粗衰减逐子独立抽取: 长 0.58~0.95、粗 0.55~0.75, 兄弟枝长短错落; 张角 0.30~0.78rad, 末端 2~3 叉, 中段侧枝概率 0.55;
// 叶: 沿途基准 P1 稀(0.06) → P2(0.26) → P3(0.48) → P4+(0.34), 每枝再乘独立疏密因子 0.5~1.5;
// 末梢端簇 0~3 片强随机(三成枝头留白); 归一化双向缩放, 保证最深梢连同下垂叶尖(≤26px)全部落在容器内(杜绝底缘平切)
import { onBeforeUnmount, onMounted, ref } from 'vue'

interface InkBranch {
  pts: number[]; birth: number; dur: number; depth: number
  width: number; coreA: number; haloA: number
}
interface InkLeaf {
  x: number; y: number; angle: number; len: number
  a: number; tone: number; born: number
}
interface InkStructure { branches: InkBranch[]; leaves: InkLeaf[] }

/** 确定性伪随机(纯函数, 随 Worker 入驻) */
function mulberry32(seed: number) {
  return () => {
    seed |= 0
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

/** 纯函数: 生成分形水墨枝(无 DOM 依赖, 可整体移入 Worker); w/h 为容器像素尺寸 */
function generateStructure(seed: number, w: number, h: number): InkStructure {
  const rng = mulberry32(seed)
  const branches: InkBranch[] = []
  const leaves: InkLeaf[] = []
  const DOWN = Math.PI / 2
  const SPEED = 0.0056 + rng() * 0.0012 // s/px: 单枝生长时长 ∝ 枝长

  const leaf = (x: number, y: number, angle: number, born: number) => {
    leaves.push({ x, y, angle, born, len: 13 + rng() * 11, a: 0.18 + rng() * 0.34, tone: rng() })
  }

  const branch = (x: number, y: number, angle: number, len: number, width: number, depth: number, birth: number) => {
    if (branches.length >= 900 || len < 10) return
    const seg = 11 + rng() * 7 // 每枝折线段长随机 → 运笔节奏枝枝不同
    const segs = Math.max(2, Math.round(len / seg))
    const gGain = 0.045 * (0.5 + depth * 0.35) // 重力项: 越细越垂
    const pts: number[] = [x, y]
    let a = angle
    let cx = x
    let cy = y
    for (let i = 0; i < segs; i++) {
      a += (DOWN - a) * gGain + (rng() - 0.5) * 0.24
      if (cx < w * 0.05) a -= 0.3 // 左缘内侧回摆, 防止出画被裁
      if (cx > w * 0.985) a += 0.3
      cx += Math.cos(a) * seg
      cy += Math.sin(a) * seg
      pts.push(cx, cy)
    }
    const dur = len * SPEED * (0.85 + rng() * 0.3)
    const coreA = Math.min(0.62, Math.max(0.2, 0.6 - depth * 0.06)) * (0.85 + rng() * 0.3)
    branches.push({ pts, birth, dur, depth, width, coreA, haloA: 0.06 + rng() * 0.05 })
    const end = birth + dur

    // 沿途挂叶: P1 稀(0.06) → P2 中(0.26) → P3 偏密(0.48) → P4+ 疏(0.34);
    // 每枝再乘独立疏密因子 0.5~1.5 → 枝与枝之间忽疏忽密;
    // 叶尖整体垂坠(参考竹叶): 以重力 90° 为主, 混入枝条走向与随机扰动
    const leafProb = (depth <= 1 ? 0.06 : depth === 2 ? 0.26 : depth === 3 ? 0.48 : 0.34) * (0.5 + rng())
    for (let i = 1; i < segs; i++) {
      if (rng() < leafProb) {
        leaf(
          pts[i * 2], pts[i * 2 + 1],
          55.8 + (a * 180) / Math.PI * 0.38 + (rng() - 0.5) * 72,
          birth + (i / segs) * dur + 0.05,
        )
      }
    }

    // 末梢: 端簇叶收笔(垂坠展开); 数量强随机 —— 三成枝头留白, 其余 1~3 片
    if (depth >= 6) {
      const r = rng()
      const n = r < 0.32 ? 0 : r < 0.72 ? 1 + Math.floor(rng() * 2) : 2 + Math.floor(rng() * 2)
      for (let i = 0; i < n; i++) {
        leaf(cx, cy, 55.8 + (a * 180) / Math.PI * 0.38 + (rng() - 0.5) * 130, end + rng() * 0.3)
      }
      return
    }

    const childBirth = end + 0.04 + rng() * 0.16 // 出生 = 父枝长成 + 40~200ms
    const fork = 0.3 + rng() * 0.48

    // 中段侧枝: 自 55%~80% 处斜出(长度/粗细独立随机, 与末端子枝错落)
    if (depth >= 1 && rng() < 0.55) {
      const idx = Math.max(1, Math.floor(segs * (0.55 + rng() * 0.25)))
      branch(
        pts[idx * 2], pts[idx * 2 + 1],
        a + fork * (rng() < 0.5 ? -1 : 1),
        len * (0.42 + rng() * 0.3), width * (0.55 + rng() * 0.2), depth + 1,
        birth + (idx / segs) * dur + 0.04 + rng() * 0.12,
      )
    }

    // 末端 2~3 叉: 每个子枝长/粗独立抽取(长 0.58~0.95), 兄弟枝长短参差
    const n = 2 + (rng() < 0.2 ? 1 : 0)
    const base = a + (rng() - 0.5) * 0.2
    for (let i = 0; i < n; i++) {
      branch(cx, cy, base + (i - (n - 1) / 2) * fork + (rng() - 0.5) * 0.14, len * (0.58 + rng() * 0.37), width * (0.55 + rng() * 0.2), depth + 1, childBirth + i * 0.05)
    }
  }

  // 入笔: 容器右上外侧, 初始方向左下≈115°, 主干长度决定整体垂坠幅度
  branch(w - 6, 4, (115 * Math.PI) / 180, h * (0.26 + rng() * 0.05), 3.2, 0, 0.05)

  // 归一化: 双向等比缩放(树冠过浅放大、过深缩小), 保证最深梢连同其下垂叶尖
  // (叶长≤24px, 留 26px 底部余量)全部落在容器内 —— 树冠超出容器时若不缩,
  // 枝叶会在 Canvas 底缘被齐切出一条水平断口, 视觉上像被下方内容截断
  let maxY = 0
  for (const b of branches) {
    for (let i = 1; i < b.pts.length; i += 2) maxY = Math.max(maxY, b.pts[i])
  }
  const s = Math.min((h - 26) / Math.max(maxY, 1), 1.35)
  if (s > 1.002 || s < 0.998) {
    for (const b of branches) {
      for (let i = 0; i < b.pts.length; i += 2) {
        b.pts[i] *= s
        b.pts[i + 1] *= s
      }
    }
    for (const l of leaves) {
      l.x *= s
      l.y *= s
    }
  }
  return { branches, leaves }
}

const rootEl = ref<HTMLElement | null>(null)
const staticEl = ref<HTMLCanvasElement | null>(null)
const dynamicEl = ref<HTMLCanvasElement | null>(null)

/** 容器高: 卡片的 120%~150%(随机), 允许墨枝垂出卡底 */
const boxH = 122 + Math.floor(Math.random() * 26)

/** Worker 源码(inline Blob): 仅注入两个纯函数 + 消息分发 */
const WORKER_SRC = `
${mulberry32.toString()}
${generateStructure.toString()}
self.onmessage = (e) => {
  const d = e.data
  self.postMessage(generateStructure(d.seed, d.w, d.h))
}
`

// ---- 运行时结构(含主线程预计算) ----
interface RTBranch extends InkBranch { cum: number[]; total: number; done: boolean }
interface RTLeaf extends InkLeaf { done: boolean }

let rt: { branches: RTBranch[]; leaves: RTLeaf[]; total: number } | null = null
let sctx: CanvasRenderingContext2D | null = null
let dctx: CanvasRenderingContext2D | null = null
let boxW = 0
let boxHpx = 0
let dpr = 1
let raf = 0
let lastT = 0
let elapsed = 0 // 已播放毫秒(visibilitychange 暂停时冻结)
let bi = 0 // 首个未完成的枝(按 birth 排序)
let li = 0 // 首个未完成的叶(按 born 排序)
let status: 'idle' | 'playing' | 'settled' = 'idle'
let hadStarted = false
let reducedMotion = false
let dark = false
let inkRGB = '26,30,36'
let sageA = '96,116,102'
let sageB = '118,140,118'
let worker: Worker | null = null
let workerURL = ''
let io: IntersectionObserver | null = null
let ro: ResizeObserver | null = null
let resizeTimer = 0
let genToken = 0
const seed = (Math.random() * 0x7fffffff) | 0

/** 尺寸画布(DPR 上限 2); 仅在挂载/重建时读布局, 帧循环内不读 */
function sizeCanvases() {
  const root = rootEl.value
  const s = staticEl.value
  const d = dynamicEl.value
  if (!root || !s || !d) return
  const rect = root.getBoundingClientRect()
  dpr = Math.min(window.devicePixelRatio || 1, 2)
  boxW = Math.max(1, rect.width)
  boxHpx = Math.max(1, rect.height)
  s.width = Math.round(boxW * dpr)
  s.height = Math.round(boxHpx * dpr)
  d.width = s.width
  d.height = s.height
  sctx = s.getContext('2d')
  dctx = d.getContext('2d')
  sctx?.setTransform(dpr, 0, 0, dpr, 0, 0)
  dctx?.setTransform(dpr, 0, 0, dpr, 0, 0)
}

/** 预计算: 排序 + 逐枝累积段长(供按进度截断绘制) */
function prepare(data: InkStructure) {
  const branches: RTBranch[] = data.branches.map(b => ({ ...b, cum: [], total: 0, done: false }))
  branches.sort((a, b) => a.birth - b.birth)
  for (const b of branches) {
    const cum: number[] = [0]
    for (let i = 2; i < b.pts.length; i += 2) {
      cum.push(cum[cum.length - 1] + Math.hypot(b.pts[i] - b.pts[i - 2], b.pts[i + 1] - b.pts[i - 1]))
    }
    b.cum = cum
    b.total = cum[cum.length - 1] || 1
  }
  const leaves: RTLeaf[] = data.leaves.map(l => ({ ...l, done: false })).sort((a, b) => a.born - b.born)
  const total = Math.max(
    branches.reduce((m, b) => Math.max(m, b.birth + b.dur), 0),
    leaves.reduce((m, l) => Math.max(m, l.born), 0),
  ) + 0.4
  return { branches, leaves, total }
}

/** 双描一笔: 淡宽墨晕(×2.8) + 浓细墨骨, 渗化全靠双描; t01 为生长进度 */
function strokeBranch(ctx: CanvasRenderingContext2D, b: RTBranch, t01: number) {
  const target = b.total * t01
  const pts = b.pts
  ctx.beginPath()
  ctx.moveTo(pts[0], pts[1])
  for (let i = 1; i < b.cum.length; i++) {
    if (b.cum[i] <= target) {
      ctx.lineTo(pts[i * 2], pts[i * 2 + 1])
      continue
    }
    const prev = b.cum[i - 1]
    const k = (target - prev) / Math.max(b.cum[i] - prev, 1e-6)
    ctx.lineTo(pts[(i - 1) * 2] + (pts[i * 2] - pts[(i - 1) * 2]) * k, pts[(i - 1) * 2 + 1] + (pts[i * 2 + 1] - pts[(i - 1) * 2 + 1]) * k)
    break
  }
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  ctx.strokeStyle = `rgba(${inkRGB},${b.haloA.toFixed(3)})`
  ctx.lineWidth = b.width * 2.8
  ctx.stroke()
  ctx.strokeStyle = `rgba(${inkRGB},${b.coreA.toFixed(3)})`
  ctx.lineWidth = b.width
  ctx.stroke()
}

/** 叶: 两段贝塞尔尖椭圆, 灰绿浓淡随机; scale 供舒展动画 */
function drawLeaf(ctx: CanvasRenderingContext2D, lf: RTLeaf, scale: number) {
  ctx.save()
  ctx.translate(lf.x, lf.y)
  ctx.rotate((lf.angle * Math.PI) / 180)
  ctx.scale(scale, scale)
  ctx.beginPath()
  ctx.moveTo(0, 0)
  ctx.quadraticCurveTo(lf.len * 0.45, -lf.len * 0.18, lf.len, 0)
  ctx.quadraticCurveTo(lf.len * 0.45, lf.len * 0.18, 0, 0)
  ctx.closePath()
  ctx.fillStyle = `rgba(${lf.tone < 0.5 ? sageA : sageB},${lf.a.toFixed(3)})`
  ctx.fill()
  ctx.restore()
}

/** easeOutBack: 叶舒展 300ms 带轻微回弹 */
function easeOutBack(t: number) {
  const c1 = 1.70158
  const c3 = c1 + 1
  return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2)
}

function finish() {
  if (raf) {
    cancelAnimationFrame(raf)
    raf = 0
  }
  if (rt && sctx && dctx) {
    for (const b of rt.branches) {
      if (!b.done) {
        strokeBranch(sctx, b, 1)
        b.done = true
      }
    }
    for (const lf of rt.leaves) {
      if (!lf.done) {
        drawLeaf(sctx, lf, 1)
        lf.done = true
      }
    }
    dctx.clearRect(0, 0, boxW, boxHpx)
  }
  status = 'settled'
}

function play() {
  if (!rt || reducedMotion || status !== 'idle') return
  status = 'playing'
  elapsed = 0
  bi = 0
  li = 0
  lastT = performance.now()
  raf = requestAnimationFrame(frame)
}

/** 帧循环: 静态层只增量盖戳, 动态层每帧清空后仅画生长中枝叶 */
function frame(now: number) {
  raf = requestAnimationFrame(frame)
  const dt = Math.min(now - lastT, 50) // dt 钳制≤50ms
  lastT = now
  elapsed += dt
  if (!rt || !sctx || !dctx) return
  const es = elapsed / 1000
  dctx.clearRect(0, 0, boxW, boxHpx)

  for (let i = bi; i < rt.branches.length; i++) {
    const b = rt.branches[i]
    if (b.birth > es) break
    if (b.done) continue
    const t = (es - b.birth) / b.dur
    if (t >= 1) {
      strokeBranch(sctx, b, 1) // 长成即盖戳进静态层
      b.done = true
    } else {
      strokeBranch(dctx, b, 1 - Math.pow(1 - t, 1.6)) // 运笔渐缓
    }
  }
  while (bi < rt.branches.length && rt.branches[bi].done) bi++

  for (let i = li; i < rt.leaves.length; i++) {
    const lf = rt.leaves[i]
    if (lf.born > es) break
    if (lf.done) continue
    const t = (es - lf.born) / 0.3
    if (t >= 1) {
      drawLeaf(sctx, lf, 1)
      lf.done = true
    } else {
      drawLeaf(dctx, lf, 0.15 + 0.85 * easeOutBack(t))
    }
  }
  while (li < rt.leaves.length && rt.leaves[li].done) li++

  if (es >= rt.total) finish()
}

/** 请求结构: Worker 优先, 失败回落 requestIdleCallback/setTimeout */
function requestStructure() {
  const w = boxW
  const h = boxHpx
  if (w < 60 || h < 60) return
  const token = genToken
  const apply = (data: InkStructure) => {
    if (token !== genToken) return
    rt = prepare(data)
    if (reducedMotion) {
      finish()
      return
    }
    if (hadStarted) play()
  }
  const fallback = () => {
    if (typeof requestIdleCallback === 'function') requestIdleCallback(() => apply(generateStructure(seed, w, h)), { timeout: 300 })
    else window.setTimeout(() => apply(generateStructure(seed, w, h)), 30)
  }
  try {
    if (!worker) {
      const blob = new Blob([WORKER_SRC], { type: 'text/javascript' })
      workerURL = URL.createObjectURL(blob)
      worker = new Worker(workerURL)
      worker.onmessage = (e: MessageEvent<InkStructure>) => apply(e.data)
      worker.onerror = () => {
        worker?.terminate()
        worker = null
        fallback()
      }
    }
    worker.postMessage({ seed, w, h })
  } catch {
    fallback()
  }
}

/** 重建: 防抖 200ms 后触发; 同 seed 重生成 → 形态一致; 已定型则直接成图 */
function rebuild() {
  genToken++
  if (raf) {
    cancelAnimationFrame(raf)
    raf = 0
  }
  const wasSettled = status === 'settled'
  status = 'idle'
  rt = null
  bi = 0
  li = 0
  sizeCanvases()
  sctx?.clearRect(0, 0, boxW, boxHpx)
  dctx?.clearRect(0, 0, boxW, boxHpx)
  const token = genToken
  const apply = (data: InkStructure) => {
    if (token !== genToken) return
    rt = prepare(data)
    if (reducedMotion || wasSettled || !hadStarted) {
      if (reducedMotion || wasSettled) finish()
      return
    }
    play()
  }
  try {
    worker?.postMessage({ seed, w: boxW, h: boxHpx })
    if (worker) {
      worker.onmessage = (e: MessageEvent<InkStructure>) => apply(e.data)
      return
    }
  } catch {
    /* 落到下方回落 */
  }
  const w = boxW
  const h = boxHpx
  const run = () => apply(generateStructure(seed, w, h))
  if (typeof requestIdleCallback === 'function') requestIdleCallback(run, { timeout: 300 })
  else window.setTimeout(run, 30)
}

function onResize() {
  window.clearTimeout(resizeTimer)
  resizeTimer = window.setTimeout(rebuild, 200)
}

/** 页面隐藏暂停 / 回来恢复(elapsed 冻结, 时间轴不跳变) */
function onVisibility() {
  if (document.hidden) {
    if (raf) {
      cancelAnimationFrame(raf)
      raf = 0
    }
  } else if (status === 'playing' && !raf && rt) {
    lastT = performance.now()
    raf = requestAnimationFrame(frame)
  }
}

onMounted(() => {
  dark = document.documentElement.classList.contains('dark')
  // 暗色纸面: 墨色反转为浅色纸墨, 叶用浅灰绿
  if (dark) {
    inkRGB = '218,226,216'
    sageA = '150,170,152'
    sageB = '186,200,180'
  }
  reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  sizeCanvases()
  requestStructure()

  // 进入视口播放一次
  io = new IntersectionObserver(
    (entries) => {
      if (entries.some(e => e.isIntersecting)) {
        hadStarted = true
        play()
        io?.disconnect()
        io = null
      }
    },
    { threshold: 0.05 },
  )
  if (rootEl.value) io.observe(rootEl.value)

  // 容器尺寸随卡片变化 → 防抖重建
  ro = new ResizeObserver(onResize)
  if (rootEl.value) ro.observe(rootEl.value)
  window.addEventListener('resize', onResize)
  document.addEventListener('visibilitychange', onVisibility)
})

onBeforeUnmount(() => {
  if (raf) cancelAnimationFrame(raf)
  window.clearTimeout(resizeTimer)
  io?.disconnect()
  ro?.disconnect()
  window.removeEventListener('resize', onResize)
  document.removeEventListener('visibilitychange', onVisibility)
  worker?.terminate()
  worker = null
  if (workerURL) URL.revokeObjectURL(workerURL)
})
</script>

<style scoped>
/* 画布叠放: 动态层在上, 静态层累积成画 */
canvas {
  display: block;
}
</style>
