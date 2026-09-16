<template>
  <!-- 俄罗斯方块: 经典 7 块旋转消行玩法, 键盘 + 触屏双操作 -->
  <GameShell title="🧱 俄罗斯方块" :score="score" :best="best">
    <template #status>
      <span class="note-sticker-tag">关卡 {{ level }}</span>
      <span class="note-sticker-tag">行数 {{ lines }}</span>
      <span class="inline-flex items-center gap-1 rounded-lg border border-note bg-note-tint px-2 py-1" title="下一块">
        <canvas ref="nextCanvas" style="width: 40px; height: 40px" />
      </span>
    </template>

    <!-- 游戏区: 主画布 + 状态覆盖层 -->
    <div relative shrink-0>
      <canvas
        ref="boardCanvas"
        class="touch-none select-none rounded-xl border-2 border-note shadow-note"
        style="height: min(480px, calc(100vh - 16rem)); aspect-ratio: 1 / 2; width: auto"
      />
      <!-- 覆盖层: 未开始/暂停/结束 -->
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
          <p class="text-2xl text-[#f5f1e6] font-bold" style="font-family: var(--note-font-hand)">游戏结束</p>
          <p class="text-sm text-[#f5f1e6]/80">本局得分 {{ score }}</p>
          <el-button type="primary" @click="start">再来一局</el-button>
        </template>
      </div>
    </div>

    <!-- 触屏虚拟按键(仅移动端) -->
    <div class="grid grid-cols-5 gap-2 w-full max-w-xs md:hidden" shrink-0>
      <button class="flex h-12 items-center justify-center rounded-note-sm border-2 border-note bg-note-card text-xl text-note-accent shadow-note select-none touch-manipulation active:bg-note-tint active:translate-y-px" @pointerdown.prevent="moveHorizontal(-1)"><span class="i-ep-arrow-left-bold" /></button>
      <button class="flex h-12 items-center justify-center rounded-note-sm border-2 border-note bg-note-card text-xl text-note-accent shadow-note select-none touch-manipulation active:bg-note-tint active:translate-y-px" @pointerdown.prevent="softDrop"><span class="i-ep-bottom" /></button>
      <button class="flex h-12 items-center justify-center rounded-note-sm border-2 border-note bg-note-card text-xl text-note-accent shadow-note select-none touch-manipulation active:bg-note-tint active:translate-y-px" @pointerdown.prevent="moveHorizontal(1)"><span class="i-ep-arrow-right-bold" /></button>
      <button class="flex h-12 items-center justify-center rounded-note-sm border-2 border-note bg-note-card text-xl text-note-accent shadow-note select-none touch-manipulation active:bg-note-tint active:translate-y-px" @pointerdown.prevent="rotateCurrent"><span class="i-ep-refresh-right" /></button>
      <button class="flex h-12 items-center justify-center rounded-note-sm border-2 border-note bg-note-card text-xl text-note-accent shadow-note select-none touch-manipulation active:bg-note-tint active:translate-y-px" @pointerdown.prevent="hardDrop"><span class="i-ep-d-arrow-right rotate-90" /></button>
    </div>

    <!-- 桌面键位说明 -->
    <p class="hidden md:block text-xs text-note-sub" shrink-0>
      ← → 移动 · ↑ 旋转 · ↓ 软降 · 空格 硬降 · P 暂停
    </p>
  </GameShell>
</template>

<script setup lang="ts">
/**
 * 俄罗斯方块页(/arcade/tetris)
 * 纯前端实现: 10x20 棋盘 + 7-bag 随机 + 幽灵投影 + 关卡加速
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import GameShell from '../components/GameShell.vue'
import { useBest } from '../composables/useBest'
import { setupCanvas } from '../utils/canvas'

// ===== 棋盘常量 =====
const COLS = 10
const ROWS = 20
const CELL = 24
const BOARD_W = COLS * CELL
const BOARD_H = ROWS * CELL

/** 方块类型(I/J/L/O/S/T/Z)与 7 种经典配色 */
const TYPES = ['I', 'J', 'L', 'O', 'S', 'T', 'Z'] as const
type PieceType = (typeof TYPES)[number]
const COLORS: Record<PieceType, string> = {
  I: '#4fc3c8', J: '#5b8def', L: '#e6b455', O: '#e8d05a',
  S: '#67c98f', T: '#b58ae0', Z: '#e07a6a',
}
/** 各类型初始矩阵(1 表示占格) */
const SHAPES: Record<PieceType, number[][]> = {
  I: [[0, 0, 0, 0], [1, 1, 1, 1], [0, 0, 0, 0], [0, 0, 0, 0]],
  J: [[1, 0, 0], [1, 1, 1], [0, 0, 0]],
  L: [[0, 0, 1], [1, 1, 1], [0, 0, 0]],
  O: [[1, 1], [1, 1]],
  S: [[0, 1, 1], [1, 1, 0], [0, 0, 0]],
  T: [[0, 1, 0], [1, 1, 1], [0, 0, 0]],
  Z: [[1, 1, 0], [0, 1, 1], [0, 0, 0]],
}
/** 消行得分表(同时消 0~4 行) */
const CLEAR_SCORE = [0, 100, 300, 500, 800]

// ===== 响应式状态 =====
type GameState = 'ready' | 'running' | 'paused' | 'over'
const state = ref<GameState>('ready')
const score = ref(0)
const lines = ref(0)
const level = computed(() => 1 + Math.floor(lines.value / 10))
const { best, submit } = useBest('tetris')
// 分数实时冲榜(仅破纪录时写盘)
watch(score, (v) => submit(v))

// ===== 非响应式对局数据(每帧读绘, 不进响应式) =====
let board: number[][] = []
let cur: { type: PieceType; matrix: number[][]; x: number; y: number } | null = null
let nextType: PieceType | null = null
let bag: PieceType[] = []
let dropAcc = 0
let rafId = 0
let lastTs = 0

/** 当前重力间隔: 关卡越高下落越快 */
function dropInterval(): number {
  return Math.max(120, 800 - (level.value - 1) * 70)
}

/** 7-bag 抽块: 每轮洗牌 7 种类型, 分布均匀 */
function drawFromBag(): PieceType {
  if (bag.length === 0) {
    bag = [...TYPES]
    for (let i = bag.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1))
      ;[bag[i], bag[j]] = [bag[j], bag[i]]
    }
  }
  return bag.pop()!
}

/** 碰撞检测: matrix 放置在 (x,y) 是否越界或压到已堆块 */
function collide(matrix: number[][], x: number, y: number): boolean {
  for (let r = 0; r < matrix.length; r++) {
    for (let c = 0; c < matrix[r].length; c++) {
      if (!matrix[r][c]) continue
      const bx = x + c
      const by = y + r
      if (bx < 0 || bx >= COLS || by >= ROWS) return true
      if (by >= 0 && board[by][bx]) return true
    }
  }
  return false
}

/** 矩阵顺时针旋转(转置后反转每行) */
function rotateMatrix(m: number[][]): number[][] {
  return m[0].map((_, c) => m.map((row) => row[c]).reverse())
}

/** 计算幽灵投影 y(硬降/画影子用) */
function ghostY(): number {
  if (!cur) return 0
  let y = cur.y
  while (!collide(cur.matrix, cur.x, y + 1)) y++
  return y
}

/** 生成新块; 出生即碰撞则游戏结束 */
function spawn() {
  const type = nextType ?? drawFromBag()
  nextType = drawFromBag()
  const matrix = SHAPES[type].map((row) => [...row])
  cur = { type, matrix, x: Math.floor((COLS - matrix[0].length) / 2), y: 0 }
  drawNext()
  if (collide(cur.matrix, cur.x, cur.y)) {
    cur = null
    state.value = 'over'
  }
}

/** 锁定当前块入棋盘, 随后消行结算并生成下一块 */
function lockPiece() {
  if (!cur) return
  cur.matrix.forEach((row, r) => {
    row.forEach((v, c) => {
      if (v && cur!.y + r >= 0) board[cur!.y + r][cur!.x + c] = TYPES.indexOf(cur!.type) + 1
    })
  })
  // 整行清除: 自下而上重建
  const kept = board.filter((row) => row.some((v) => !v))
  const cleared = ROWS - kept.length
  if (cleared > 0) {
    board = Array.from({ length: cleared }, () => Array(COLS).fill(0)).concat(kept)
    lines.value += cleared
    score.value += CLEAR_SCORE[cleared] * level.value
  }
  cur = null
  spawn()
}

/** 左右移动 */
function moveHorizontal(dx: number) {
  if (state.value !== 'running' || !cur) return
  if (!collide(cur.matrix, cur.x + dx, cur.y)) cur.x += dx
}

/** 软降: 下移一格, 成功加 1 分, 触底则锁定 */
function softDrop() {
  if (state.value !== 'running' || !cur) return
  if (!collide(cur.matrix, cur.x, cur.y + 1)) {
    cur.y++
    score.value++
  } else {
    lockPiece()
  }
}

/** 硬降: 直落到底并锁定, 每行加 2 分 */
function hardDrop() {
  if (state.value !== 'running' || !cur) return
  const target = ghostY()
  score.value += (target - cur.y) * 2
  cur.y = target
  lockPiece()
}

/** 旋转(带简单踢墙: 依次尝试原位/左移/右移/远移) */
function rotateCurrent() {
  if (state.value !== 'running' || !cur || cur.type === 'O') return
  const rotated = rotateMatrix(cur.matrix)
  for (const kick of [0, -1, 1, -2, 2]) {
    if (!collide(rotated, cur.x + kick, cur.y)) {
      cur.matrix = rotated
      cur.x += kick
      return
    }
  }
}

// ===== 绘制 =====
const boardCanvas = ref<HTMLCanvasElement>()
const nextCanvas = ref<HTMLCanvasElement>()
let ctx: CanvasRenderingContext2D | null = null
let nextCtx: CanvasRenderingContext2D | null = null

/** 绘一个像素方块(内亮边营造复古凸起) */
function drawCell(c: CanvasRenderingContext2D, x: number, y: number, size: number, color: string) {
  c.fillStyle = color
  c.fillRect(x, y, size, size)
  c.fillStyle = 'rgba(255,255,255,0.3)'
  c.fillRect(x, y, size, Math.max(2, size * 0.16))
  c.fillStyle = 'rgba(0,0,0,0.18)'
  c.fillRect(x, y + size - Math.max(2, size * 0.16), size, Math.max(2, size * 0.16))
}

/** 绘主画布: 暗屏网格 + 已堆块 + 幽灵 + 当前块 */
function render() {
  // 局部常量收窄: 闭包内使用可空模块变量会丢失判空
  const c2d = ctx
  if (!c2d) return
  c2d.fillStyle = '#20302a'
  c2d.fillRect(0, 0, BOARD_W, BOARD_H)
  c2d.strokeStyle = 'rgba(255,255,255,0.05)'
  for (let i = 1; i < COLS; i++) {
    c2d.beginPath(); c2d.moveTo(i * CELL, 0); c2d.lineTo(i * CELL, BOARD_H); c2d.stroke()
  }
  for (let j = 1; j < ROWS; j++) {
    c2d.beginPath(); c2d.moveTo(0, j * CELL); c2d.lineTo(BOARD_W, j * CELL); c2d.stroke()
  }
  // 已堆块
  for (let r = 0; r < ROWS; r++) {
    for (let col = 0; col < COLS; col++) {
      const v = board[r][col]
      if (v) drawCell(c2d, col * CELL, r * CELL, CELL, COLORS[TYPES[v - 1]])
    }
  }
  // 幽灵投影 + 当前块
  if (cur) {
    const gy = ghostY()
    c2d.strokeStyle = `${COLORS[cur.type]}55`
    c2d.lineWidth = 2
    cur.matrix.forEach((row, r) => {
      row.forEach((v, col) => {
        if (v && gy + r >= 0) c2d.strokeRect((cur!.x + col) * CELL + 1, (gy + r) * CELL + 1, CELL - 2, CELL - 2)
      })
    })
    cur.matrix.forEach((row, r) => {
      row.forEach((v, col) => {
        if (v && cur!.y + r >= 0) drawCell(c2d, (cur!.x + col) * CELL, (cur!.y + r) * CELL, CELL, COLORS[cur!.type])
      })
    })
  }
}

/** 绘"下一块"预览(开局前无预览块时留空屏) */
function drawNext() {
  if (!nextCtx || !nextType) return
  const size = 40
  nextCtx.fillStyle = '#20302a'
  nextCtx.fillRect(0, 0, size, size)
  const m = SHAPES[nextType]
  // 预览居中: 计算矩阵实际占格范围
  const filled = m.flatMap((row, r) => row.map((v, c) => (v ? [r, c] : null)).filter(Boolean) as [number, number][])
  const minR = Math.min(...filled.map(([r]) => r))
  const maxR = Math.max(...filled.map(([r]) => r))
  const minC = Math.min(...filled.map(([, c]) => c))
  const maxC = Math.max(...filled.map(([, c]) => c))
  const cell = 9
  const offX = (size - (maxC - minC + 1) * cell) / 2
  const offY = (size - (maxR - minR + 1) * cell) / 2
  for (const [r, c] of filled) {
    drawCell(nextCtx, offX + (c - minC) * cell, offY + (r - minR) * cell, cell, COLORS[nextType])
  }
}

// ===== 主循环: 固定读 dt, 仅 running 时推进重力 =====
function loop(ts: number) {
  rafId = requestAnimationFrame(loop)
  const dt = Math.min(100, ts - lastTs)
  lastTs = ts
  if (state.value === 'running' && cur) {
    dropAcc += dt
    if (dropAcc >= dropInterval()) {
      dropAcc = 0
      softDrop()
    }
  }
  render()
}

// ===== 开局/暂停/继续 =====
function start() {
  // 失焦覆盖层按钮: 避免游戏中的空格键再次触发按钮点击导致重开
  ;(document.activeElement as HTMLElement | null)?.blur()
  board = Array.from({ length: ROWS }, () => Array(COLS).fill(0))
  score.value = 0
  lines.value = 0
  bag = []
  nextType = null
  dropAcc = 0
  spawn()
  state.value = 'running'
}
function resume() {
  if (state.value === 'paused') state.value = 'running'
}

// ===== 键盘控制 =====
function onKeyDown(e: KeyboardEvent) {
  switch (e.code) {
    case 'ArrowLeft': e.preventDefault(); moveHorizontal(-1); break
    case 'ArrowRight': e.preventDefault(); moveHorizontal(1); break
    case 'ArrowDown': e.preventDefault(); softDrop(); break
    case 'ArrowUp': e.preventDefault(); rotateCurrent(); break
    case 'Space':
      e.preventDefault()
      if (state.value === 'ready' || state.value === 'over') start()
      else hardDrop()
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
  nextCtx = setupCanvas(nextCanvas.value!, 40, 40)
  board = Array.from({ length: ROWS }, () => Array(COLS).fill(0))
  drawNext()
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
