<template>
  <!-- 打砖块: 弹板反弹击碎砖阵, 鼠标/触屏拖动或方向键操控 -->
  <GameShell title="🎯 打砖块" :score="score" :best="best">
    <template #status>
      <span class="note-sticker-tag">关卡 {{ level }}</span>
      <span class="note-sticker-tag">❤️ {{ lives }}</span>
    </template>

    <!-- 游戏区: 主画布 + 状态覆盖层 -->
    <div relative shrink-0 w-full max-w-120>
      <canvas
        ref="boardCanvas"
        class="touch-none select-none rounded-xl border-2 border-note shadow-note w-full"
        style="aspect-ratio: 4 / 3"
        @pointermove="onPointerMove"
        @pointerdown="onPointerDown"
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
            {{ win ? '砖块全清, 太强了!' : '游戏结束' }}
          </p>
          <p class="text-sm text-[#f5f1e6]/80">本局得分 {{ score }}</p>
          <el-button type="primary" @click="start">再来一局</el-button>
        </template>
      </div>
    </div>

    <!-- 触屏/辅助按键(仅移动端): 左右移动 + 发射 -->
    <div class="grid grid-cols-3 gap-2 w-full max-w-xs md:hidden" shrink-0>
      <button class="flex h-12 items-center justify-center rounded-note-sm border-2 border-note bg-note-card text-xl text-note-accent shadow-note select-none touch-manipulation active:bg-note-tint active:translate-y-px" @pointerdown.prevent="padLeft = true" @pointerup="padLeft = false" @pointercancel="padLeft = false">
        <span class="i-ep-arrow-left-bold" />
      </button>
      <button class="flex h-12 items-center justify-center rounded-note-sm border-2 border-note bg-note-card text-xl text-note-accent shadow-note select-none touch-manipulation active:bg-note-tint active:translate-y-px" @pointerdown.prevent="launchOrStart"><span class="i-ep-video-play" /></button>
      <button class="flex h-12 items-center justify-center rounded-note-sm border-2 border-note bg-note-card text-xl text-note-accent shadow-note select-none touch-manipulation active:bg-note-tint active:translate-y-px" @pointerdown.prevent="padRight = true" @pointerup="padRight = false" @pointercancel="padRight = false">
        <span class="i-ep-arrow-right-bold" />
      </button>
    </div>

    <!-- 桌面操作说明 -->
    <p class="hidden md:block text-xs text-note-sub" shrink-0>
      鼠标移动弹板 · 空格/点击 发射 · ← → 微调 · P 暂停
    </p>
  </GameShell>
</template>

<script setup lang="ts">
/**
 * 打砖块页(/arcade/breakout)
 * 纯前端实现: 6x10 砖阵 + 弹板角度反弹 + 关卡加速, 三条命
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import GameShell from '../components/GameShell.vue'
import { useBest } from '../composables/useBest'
import { setupCanvas } from '../utils/canvas'

// ===== 场地常量(逻辑像素) =====
const W = 480
const H = 360
const PADDLE_W = 72
const PADDLE_H = 10
const PADDLE_Y = H - 24
const BALL_R = 5
const BRICK_ROWS = 6
const BRICK_COLS = 10
const BRICK_W = 42
const BRICK_H = 16
const BRICK_GAP = 4
const BRICK_TOP = 40
const BRICK_LEFT = (W - (BRICK_COLS * BRICK_W + (BRICK_COLS - 1) * BRICK_GAP)) / 2
/** 每行砖块配色(顶行分值最高) */
const ROW_COLORS = ['#e07a6a', '#e6b455', '#e8d05a', '#67c98f', '#5b8def', '#b58ae0']

// ===== 响应式状态 =====
type GameState = 'ready' | 'running' | 'paused' | 'over'
const state = ref<GameState>('ready')
const score = ref(0)
const lives = ref(3)
const level = ref(1)
/** 是否通关(打满 3 关后胜利收场) */
const win = ref(false)
const { best, submit } = useBest('breakout')
watch(score, (v) => submit(v))

// ===== 非响应式对局数据 =====
const paddle = { x: (W - PADDLE_W) / 2 }
const ball = { x: 0, y: 0, vx: 0, vy: 0 }
/** 球粘在弹板上待发射 */
let stuck = true
const bricksAlive: boolean[][] = []
let bricksLeft = 0
/** 键盘按住方向 + 触屏左右按住(ref: 模板事件内可写) */
const keys = new Set<string>()
const padLeft = ref(false)
const padRight = ref(false)
let rafId = 0
let lastTs = 0

/** 当前球速(随关卡提升) */
function ballSpeed(): number {
  return 240 + (level.value - 1) * 40
}
/** 每行砖块分值: 顶行 60, 逐行递减 10 */
function brickPoints(r: number): number {
  return (BRICK_ROWS - r) * 10
}

/** 重建当前关砖阵 */
function buildBricks() {
  for (let r = 0; r < BRICK_ROWS; r++) {
    bricksAlive[r] = Array.from({ length: BRICK_COLS }, () => true)
  }
  bricksLeft = BRICK_ROWS * BRICK_COLS
}

/** 球归位到弹板上待发射, 朝上随机小角度 */
function resetBall() {
  stuck = true
  ball.x = paddle.x + PADDLE_W / 2
  ball.y = PADDLE_Y - BALL_R - 1
  const angle = (Math.random() * 0.6 - 0.3)
  ball.vx = ballSpeed() * Math.sin(angle)
  ball.vy = -ballSpeed() * Math.cos(angle)
}

/** 发射粘着的球(或覆盖层时开局) */
function launchOrStart() {
  if (state.value === 'ready' || state.value === 'over') start()
  else if (state.value === 'running' && stuck) stuck = false
}

// ===== 输入: 指针拖动弹板 =====
const boardCanvas = ref<HTMLCanvasElement>()
let ctx: CanvasRenderingContext2D | null = null

/** 指针移动 → 弹板中心跟随(CSS 坐标换算逻辑坐标) */
function onPointerMove(e: PointerEvent) {
  if (state.value !== 'running') return
  const rect = boardCanvas.value!.getBoundingClientRect()
  const x = ((e.clientX - rect.left) / rect.width) * W
  paddle.x = Math.max(0, Math.min(W - PADDLE_W, x - PADDLE_W / 2))
  // 待发射时球跟随弹板
  if (stuck) {
    ball.x = paddle.x + PADDLE_W / 2
    ball.y = PADDLE_Y - BALL_R - 1
  }
}

/** 点击画布: 发射/开局 */
function onPointerDown() {
  if (state.value === 'running') launchOrStart()
}

// ===== 物理推进 =====
function step(dt: number) {
  const sec = dt / 1000
  // 键盘/按住键移动弹板
  const move = (keys.has('ArrowLeft') || padLeft.value ? -1 : 0) + (keys.has('ArrowRight') || padRight.value ? 1 : 0)
  if (move !== 0) {
    paddle.x = Math.max(0, Math.min(W - PADDLE_W, paddle.x + move * 360 * sec))
    if (stuck) {
      ball.x = paddle.x + PADDLE_W / 2
      ball.y = PADDLE_Y - BALL_R - 1
    }
  }
  if (stuck) return

  // 球运动
  ball.x += ball.vx * sec
  ball.y += ball.vy * sec

  // 墙壁反弹(左右/顶)
  if (ball.x - BALL_R < 0) { ball.x = BALL_R; ball.vx = Math.abs(ball.vx) }
  if (ball.x + BALL_R > W) { ball.x = W - BALL_R; ball.vx = -Math.abs(ball.vx) }
  if (ball.y - BALL_R < 0) { ball.y = BALL_R; ball.vy = Math.abs(ball.vy) }

  // 弹板反弹: 按命中偏移角改变出射方向
  if (
    ball.vy > 0 &&
    ball.y + BALL_R >= PADDLE_Y && ball.y - BALL_R <= PADDLE_Y + PADDLE_H &&
    ball.x >= paddle.x - BALL_R && ball.x <= paddle.x + PADDLE_W + BALL_R
  ) {
    ball.y = PADDLE_Y - BALL_R
    const rel = Math.max(-1, Math.min(1, (ball.x - (paddle.x + PADDLE_W / 2)) / (PADDLE_W / 2)))
    const theta = rel * (Math.PI / 3)
    const speed = ballSpeed()
    ball.vx = speed * Math.sin(theta)
    ball.vy = -speed * Math.cos(theta)
  }

  // 砖块碰撞: 命中即碎, 取重叠更小的轴反弹
  for (let r = 0; r < BRICK_ROWS; r++) {
    for (let c = 0; c < BRICK_COLS; c++) {
      if (!bricksAlive[r][c]) continue
      const bx = BRICK_LEFT + c * (BRICK_W + BRICK_GAP)
      const by = BRICK_TOP + r * (BRICK_H + BRICK_GAP)
      if (ball.x + BALL_R > bx && ball.x - BALL_R < bx + BRICK_W && ball.y + BALL_R > by && ball.y - BALL_R < by + BRICK_H) {
        bricksAlive[r][c] = false
        bricksLeft--
        score.value += brickPoints(r)
        const overlapX = Math.min(ball.x + BALL_R - bx, bx + BRICK_W - (ball.x - BALL_R))
        const overlapY = Math.min(ball.y + BALL_R - by, by + BRICK_H - (ball.y - BALL_R))
        if (overlapX < overlapY) ball.vx = -ball.vx
        else ball.vy = -ball.vy
        // 通关判定: 本关砖块清空 → 下一关(3 关后胜利)
        if (bricksLeft === 0) {
          if (level.value >= 3) {
            win.value = true
            state.value = 'over'
          } else {
            level.value++
            buildBricks()
            resetBall()
          }
        }
        return
      }
    }
  }

  // 落底: 扣一条命, 仍有命则重置待发射
  if (ball.y - BALL_R > H) {
    lives.value--
    if (lives.value <= 0) {
      state.value = 'over'
    } else {
      resetBall()
    }
  }
}

// ===== 绘制 =====

/** 绘一块砖: 圆角 + 顶部内亮边 */
function drawBrick(c: CanvasRenderingContext2D, x: number, y: number, color: string) {
  c.fillStyle = color
  c.beginPath()
  c.roundRect(x, y, BRICK_W, BRICK_H, 4)
  c.fill()
  c.fillStyle = 'rgba(255,255,255,0.25)'
  c.beginPath()
  c.roundRect(x + 2, y + 2, BRICK_W - 4, 4, 2)
  c.fill()
}

/** 绘主画布: 暗屏 + 砖阵 + 弹板 + 球 */
function render() {
  if (!ctx) return
  ctx.fillStyle = '#20302a'
  ctx.fillRect(0, 0, W, H)
  for (let r = 0; r < BRICK_ROWS; r++) {
    for (let c = 0; c < BRICK_COLS; c++) {
      if (bricksAlive[r]?.[c]) {
        drawBrick(ctx, BRICK_LEFT + c * (BRICK_W + BRICK_GAP), BRICK_TOP + r * (BRICK_H + BRICK_GAP), ROW_COLORS[r])
      }
    }
  }
  // 弹板
  ctx.fillStyle = '#d8d2c2'
  ctx.beginPath()
  ctx.roundRect(paddle.x, PADDLE_Y, PADDLE_W, PADDLE_H, 5)
  ctx.fill()
  // 球(待发射时上方画小箭头提示)
  ctx.fillStyle = '#f5f1e6'
  ctx.beginPath()
  ctx.arc(ball.x, ball.y, BALL_R, 0, Math.PI * 2)
  ctx.fill()
  if (stuck && state.value === 'running') {
    ctx.fillStyle = 'rgba(245,241,230,0.55)'
    ctx.beginPath()
    ctx.moveTo(ball.x, ball.y - 14)
    ctx.lineTo(ball.x - 5, ball.y - 22)
    ctx.lineTo(ball.x + 5, ball.y - 22)
    ctx.closePath()
    ctx.fill()
  }
}

// ===== 主循环 =====
function loop(ts: number) {
  rafId = requestAnimationFrame(loop)
  const dt = Math.min(32, ts - lastTs)
  lastTs = ts
  if (state.value === 'running') step(dt)
  render()
}

// ===== 开局/暂停/继续 =====
function start() {
  // 失焦覆盖层按钮: 避免游戏中的空格键再次触发按钮点击导致重开
  ;(document.activeElement as HTMLElement | null)?.blur()
  score.value = 0
  lives.value = 3
  level.value = 1
  win.value = false
  buildBricks()
  resetBall()
  state.value = 'running'
}
function resume() {
  if (state.value === 'paused') state.value = 'running'
}

// ===== 键盘控制 =====
function onKeyDown(e: KeyboardEvent) {
  if (e.code === 'ArrowLeft' || e.code === 'ArrowRight') {
    e.preventDefault()
    keys.add(e.code)
    return
  }
  switch (e.code) {
    case 'Space':
      e.preventDefault()
      if (state.value === 'ready' || state.value === 'over') start()
      else launchOrStart()
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
function onKeyUp(e: KeyboardEvent) {
  keys.delete(e.code)
}

onMounted(() => {
  ctx = setupCanvas(boardCanvas.value!, W, H)
  // 初始摆好砖阵与球, 未开局画面不空
  buildBricks()
  resetBall()
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
  // 全局抬指兜底: 按键在按钮外松开也能停止移动
  window.addEventListener('pointerup', clearPad)
  window.addEventListener('pointercancel', clearPad)
  rafId = requestAnimationFrame((ts) => {
    lastTs = ts
    loop(ts)
  })
})

onUnmounted(() => {
  cancelAnimationFrame(rafId)
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
  window.removeEventListener('pointerup', clearPad)
  window.removeEventListener('pointercancel', clearPad)
})

/** 松开任意指针时清掉触屏按住状态 */
function clearPad() {
  padLeft.value = false
  padRight.value = false
}
</script>
