<template>
  <!-- 贪吃蛇: 经典网格吃果玩法, 越吃越长越快, 键盘 + 触屏双操作 -->
  <GameShell title="🐍 贪吃蛇" :score="score" :best="best">
    <template #status>
      <span class="note-sticker-tag">长度 {{ length }}</span>
    </template>

    <!-- 游戏区: 主画布 + 状态覆盖层 -->
    <div relative shrink-0>
      <canvas
        ref="boardCanvas"
        class="touch-none select-none rounded-xl border-2 border-note shadow-note aspect-square w-auto max-md:h-[min(420px,calc(100dvh-18rem))] md:h-[min(420px,calc(100vh-16rem))]"
      />
      <div
        v-if="state !== 'running'"
        class="absolute inset-0 flex flex-col items-center justify-center gap-3 rounded-xl bg-[rgba(20,30,26,0.72)] text-center"
      >
        <template v-if="state === 'ready'">
          <p class="text-2xl text-[#f5f1e6] font-bold" style="font-family: var(--note-font-hand)">准备好了吗?</p>
          <el-button type="primary" @click="start">开始游戏</el-button>
        </template>
        <template v-else-if="state === 'paused'">
          <p class="text-2xl text-[#f5f1e6] font-bold" style="font-family: var(--note-font-hand)">已暂停</p>
          <el-button type="primary" @click="resume">继续</el-button>
        </template>
        <template v-else>
          <p class="text-2xl text-[#f5f1e6] font-bold" style="font-family: var(--note-font-hand)">
            {{ win ? '吃满全场, 无敌了!' : '游戏结束' }}
          </p>
          <p class="text-sm text-[#f5f1e6]/80">本局得分 {{ score }}</p>
          <el-button type="primary" @click="start">再来一局</el-button>
        </template>
      </div>
    </div>

    <!-- 触屏方向键(仅移动端): 十字布局 -->
    <div class="grid grid-cols-3 gap-2 w-44 md:hidden" shrink-0>
      <span />
      <button class="flex h-12 items-center justify-center rounded-note-sm border-2 border-note bg-note-card text-xl text-note-accent shadow-note select-none touch-manipulation active:bg-note-tint active:translate-y-px" @pointerdown.prevent="queueDir(0, -1)"><span class="i-ep-caret-top" /></button>
      <span />
      <button class="flex h-12 items-center justify-center rounded-note-sm border-2 border-note bg-note-card text-xl text-note-accent shadow-note select-none touch-manipulation active:bg-note-tint active:translate-y-px" @pointerdown.prevent="queueDir(-1, 0)"><span class="i-ep-caret-left" /></button>
      <button class="flex h-12 items-center justify-center rounded-note-sm border-2 border-note bg-note-card text-xl text-note-accent shadow-note select-none touch-manipulation active:bg-note-tint active:translate-y-px" @pointerdown.prevent="queueDir(1, 0)"><span class="i-ep-caret-right" /></button>
      <button class="flex h-12 items-center justify-center rounded-note-sm border-2 border-note bg-note-card text-xl text-note-accent shadow-note select-none touch-manipulation active:bg-note-tint active:translate-y-px" @pointerdown.prevent="queueDir(0, 1)"><span class="i-ep-caret-bottom" /></button>
    </div>

    <!-- 桌面键位说明 -->
    <p class="hidden md:block text-xs text-note-sub" shrink-0>
      方向键 / WASD 转向 · 空格 开始 · P 暂停
    </p>
  </GameShell>
</template>

<script setup lang="ts">
/**
 * 贪吃蛇页(/arcade/snake)
 * 纯前端实现: 21x21 网格 + 方向缓冲队列 + 吃果加速
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import GameShell from '../components/GameShell.vue'
import { useBest } from '../composables/useBest'
import { setupCanvas } from '../utils/canvas'

// ===== 棋盘常量 =====
const N = 21
const CELL = 20
const BOARD_W = N * CELL
const BOARD_H = N * CELL

// ===== 响应式状态 =====
type GameState = 'ready' | 'running' | 'paused' | 'over'
const state = ref<GameState>('ready')
const score = ref(0)
const length = computed(() => snake.length)
/** 是否通关(蛇身铺满全场) */
const win = ref(false)
const { best, submit } = useBest('snake')
watch(score, (v) => submit(v))

// ===== 非响应式对局数据 =====
interface Cell { x: number; y: number }
const snake: Cell[] = []
let dir: Cell = { x: 1, y: 0 }
/** 方向缓冲: 一次 tick 最多转向两次, 防止高速时 180 度回头 */
const dirQueue: Cell[] = []
let food: Cell = { x: 0, y: 0 }
let foodsEaten = 0
let stepAcc = 0
let rafId = 0
let lastTs = 0

/** 当前步进间隔: 每吃 1 果加速 4ms, 下限 70ms */
function stepInterval(): number {
  return Math.max(70, 150 - foodsEaten * 4)
}

/** 在空格中随机放果子(蛇身占格除外); 无空格返回 false(通关) */
function placeFood(): boolean {
  const free: Cell[] = []
  const occupied = new Set(snake.map((c) => `${c.x},${c.y}`))
  for (let y = 0; y < N; y++) {
    for (let x = 0; x < N; x++) {
      if (!occupied.has(`${x},${y}`)) free.push({ x, y })
    }
  }
  if (free.length === 0) return false
  food = free[Math.floor(Math.random() * free.length)]
  return true
}

/** 排队转向: 与队尾/当前方向相反或相同的输入直接忽略 */
function queueDir(x: number, y: number) {
  if (state.value !== 'running') return
  const last = dirQueue.length ? dirQueue[dirQueue.length - 1] : dir
  if ((x === -last.x && y === -last.y) || (x === last.x && y === last.y)) return
  if (dirQueue.length < 2) dirQueue.push({ x, y })
}

/** 单步推进: 出队转向 → 新头 → 撞墙/撞己判负 → 吃果生长 */
function step() {
  if (dirQueue.length) dir = dirQueue.shift()!
  const head = { x: snake[0].x + dir.x, y: snake[0].y + dir.y }
  // 撞墙
  if (head.x < 0 || head.x >= N || head.y < 0 || head.y >= N) {
    state.value = 'over'
    return
  }
  const eating = head.x === food.x && head.y === food.y
  // 不吃果时尾巴会挪走, 故尾巴格可通过
  if (!eating) snake.pop()
  // 撞己判负(覆盖层接管画面, 无需还原尾巴)
  if (snake.some((c) => c.x === head.x && c.y === head.y)) {
    state.value = 'over'
    return
  }
  snake.unshift(head)
  if (eating) {
    foodsEaten++
    score.value += 10
    if (!placeFood()) win.value = true
  }
}

// ===== 绘制 =====
const boardCanvas = ref<HTMLCanvasElement>()
let ctx: CanvasRenderingContext2D | null = null

/** 绘一节蛇身: 圆角方块, 头部带眼 */
function drawSnakeCell(c: CanvasRenderingContext2D, x: number, y: number, isHead: boolean, t: number) {
  const pad = 1
  c.fillStyle = isHead
    ? '#a8e6b0'
    : `rgba(103, 201, 143, ${Math.max(0.45, 1 - t * 0.55)})`
  c.beginPath()
  c.roundRect(x * CELL + pad, y * CELL + pad, CELL - pad * 2, CELL - pad * 2, 5)
  c.fill()
  if (isHead) {
    // 依据朝向画两只眼: 头中心沿朝向前偏, 两眼横向排布
    c.fillStyle = '#20302a'
    const cx = x * CELL + CELL / 2
    const cy = y * CELL + CELL / 2
    const e1: [number, number] = dir.x !== 0 ? [cx + dir.x * 3, cy - 3.5] : [cx - 3.5, cy + dir.y * 3]
    const e2: [number, number] = dir.x !== 0 ? [cx + dir.x * 3, cy + 3.5] : [cx + 3.5, cy + dir.y * 3]
    c.beginPath()
    c.arc(e1[0], e1[1], 1.8, 0, Math.PI * 2)
    c.arc(e2[0], e2[1], 1.8, 0, Math.PI * 2)
    c.fill()
  }
}

/** 绘主画布: 暗屏网格 + 果子 + 蛇身 */
function render() {
  if (!ctx) return
  ctx.fillStyle = '#20302a'
  ctx.fillRect(0, 0, BOARD_W, BOARD_H)
  ctx.strokeStyle = 'rgba(255,255,255,0.05)'
  for (let i = 1; i < N; i++) {
    ctx.beginPath(); ctx.moveTo(i * CELL, 0); ctx.lineTo(i * CELL, BOARD_H); ctx.stroke()
    ctx.beginPath(); ctx.moveTo(0, i * CELL); ctx.lineTo(BOARD_W, i * CELL); ctx.stroke()
  }
  // 果子: 红果 + 小叶
  ctx.fillStyle = '#e07a6a'
  ctx.beginPath()
  ctx.arc(food.x * CELL + CELL / 2, food.y * CELL + CELL / 2 + 1, 6, 0, Math.PI * 2)
  ctx.fill()
  ctx.fillStyle = '#67c98f'
  ctx.fillRect(food.x * CELL + CELL / 2 - 1, food.y * CELL + CELL / 2 - 8, 3, 4)
  // 蛇身(头亮尾暗)
  for (let i = snake.length - 1; i >= 0; i--) {
    drawSnakeCell(ctx, snake[i].x, snake[i].y, i === 0, i / Math.max(1, snake.length - 1))
  }
}

// ===== 主循环 =====
function loop(ts: number) {
  rafId = requestAnimationFrame(loop)
  const dt = Math.min(100, ts - lastTs)
  lastTs = ts
  if (state.value === 'running') {
    stepAcc += dt
    if (stepAcc >= stepInterval()) {
      stepAcc = 0
      step()
    }
  }
  render()
}

// ===== 开局/暂停/继续 =====
function start() {
  // 失焦覆盖层按钮: 避免游戏中的空格键再次触发按钮点击导致重开
  ;(document.activeElement as HTMLElement | null)?.blur()
  snake.length = 0
  const mid = Math.floor(N / 2)
  snake.push({ x: mid, y: mid }, { x: mid - 1, y: mid }, { x: mid - 2, y: mid })
  dir = { x: 1, y: 0 }
  dirQueue.length = 0
  foodsEaten = 0
  score.value = 0
  win.value = false
  stepAcc = 0
  placeFood()
  state.value = 'running'
}
function resume() {
  if (state.value === 'paused') state.value = 'running'
}

// ===== 键盘控制 =====
function onKeyDown(e: KeyboardEvent) {
  const dirKeys: Record<string, [number, number]> = {
    ArrowLeft: [-1, 0], KeyA: [-1, 0],
    ArrowRight: [1, 0], KeyD: [1, 0],
    ArrowUp: [0, -1], KeyW: [0, -1],
    ArrowDown: [0, 1], KeyS: [0, 1],
  }
  if (dirKeys[e.code]) {
    e.preventDefault()
    queueDir(...dirKeys[e.code])
    return
  }
  switch (e.code) {
    case 'Space':
      e.preventDefault()
      if (state.value === 'ready' || state.value === 'over') start()
      else if (state.value === 'paused') resume()
      else state.value = 'paused'
      break
    case 'KeyP':
      e.preventDefault()
      if (state.value === 'running') state.value = 'paused'
      else if (state.value === 'paused') resume()
      break
    case 'Enter':
      if (state.value === 'ready' || state.value === 'over') start()
      break
  }
}

onMounted(() => {
  ctx = setupCanvas(boardCanvas.value!, BOARD_W, BOARD_H)
  // 初始摆一条展示蛇, 便于未开局时画面不空
  const mid = Math.floor(N / 2)
  snake.push({ x: mid, y: mid }, { x: mid - 1, y: mid }, { x: mid - 2, y: mid })
  placeFood()
  window.addEventListener('keydown', onKeyDown)
  rafId = requestAnimationFrame((ts) => {
    lastTs = ts
    loop(ts)
  })
})

onUnmounted(() => {
  cancelAnimationFrame(rafId)
  window.removeEventListener('keydown', onKeyDown)
})
</script>
