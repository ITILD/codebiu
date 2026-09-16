<template>
  <!-- 游戏大厅: Switch 主机选卡风格 —— 居中大卡片, 悬停放大高亮, 卡面为像素风预览画布 -->
  <div flex flex-col h-app w-full bg-note-paper overflow-hidden>
    <!-- 页头: 返回首页 + 主机铭牌 -->
    <header bg-note-gradient px-4 md:px-6 py-3 border-b border-note shrink-0>
      <div flex items-center gap-3>
        <RouterLink
          to="/"
          class="note-transition inline-flex items-center gap-1 rounded-lg border border-note bg-note-card px-2.5 py-1.5 text-xs font-medium text-note-sub hover:text-note-green hover:border-note-green"
          title="返回首页"
        >
          <span class="i-ep-arrow-left" text-sm />
          首页
        </RouterLink>
        <div>
          <h1 text-lg md:text-xl font-bold text-note style="font-family: var(--note-font-hand)">
            🎮 小霸王游戏机
          </h1>
          <p text-xs text-note-sub mt-0.5>选一张卡带, 按下 START 开机</p>
        </div>
        <span class="note-sticker-tag ml-auto hidden md:inline-flex">INSERT COIN 🪙</span>
      </div>
    </header>

    <!-- 主体: 居中游戏卡带(移动端单列, 桌面三列) -->
    <main flex-1 min-h-0 overflow-y-auto flex items-center justify-center p-4>
      <div grid grid-cols-1 sm:grid-cols-3 gap-5 md:gap-7 w-full max-w-4xl>
        <RouterLink
          v-for="g in games"
          :key="g.key"
          :to="g.path"
          class="paper-grain note-transition group relative flex flex-col overflow-hidden rounded-2xl border-2 border-note bg-note-card shadow-note hover:-translate-y-1.5 hover:border-note-green hover:shadow-note-hover"
        >
          <!-- 卡带像素预览画布(手绘场景, 无图片依赖) -->
          <div class="bg-[#20302a] p-3">
            <canvas
              :ref="(el) => setPreviewRef(el, g.key)"
              :width="PREVIEW_W * 2"
              :height="PREVIEW_H * 2"
              class="w-full rounded-lg"
              style="image-rendering: pixelated"
            />
          </div>
          <!-- 卡带信息 -->
          <div p-4 flex-1 flex flex-col>
            <h3 text-lg font-bold text-note group-hover:text-note-green>{{ g.title }}</h3>
            <p text-xs text-note-sub mt-1 leading-relaxed>{{ g.desc }}</p>
            <div mt-3 flex items-center justify-between>
              <span class="note-sticker-tag">
                <span class="i-ep-trophy" text-xs />
                最高 {{ bestOf(g.key) }}
              </span>
              <span
                text-xs font-bold text-note-green opacity-0 group-hover:opacity-100 note-transition
                style="font-family: var(--note-font-hand)"
              >
                ▶ START
              </span>
            </div>
          </div>
        </RouterLink>
      </div>
    </main>

    <!-- 页脚: 通用操作说明 -->
    <footer shrink-0 px-4 pb-3 text-center text-xs text-note-sub>
      键盘: 方向键移动 · 空格加速/发射 · P 暂停 &nbsp;|&nbsp; 触屏: 页面内虚拟按键与拖动
    </footer>
  </div>
</template>

<script setup lang="ts">
/**
 * 游戏大厅页(/arcade): Switch 风格游戏选卡
 * 卡面预览为 canvas 手绘像素场景; 各卡最高分读取本地存档
 */
import { onMounted } from 'vue'
import { useBest } from '../composables/useBest'

/** 预览画布逻辑尺寸(绘制时以 2x 像素风放大) */
const PREVIEW_W = 200
const PREVIEW_H = 110

/** 游戏目录(key 与本地最高分存档键一致) */
const games = [
  { key: 'tetris', path: '/arcade/tetris', title: '俄罗斯方块', desc: '旋转堆叠消行, 手速与规划缺一不可' },
  { key: 'snake', path: '/arcade/snake', title: '贪吃蛇', desc: '吞下果子不断变长, 撞墙撞己即终' },
  { key: 'breakout', path: '/arcade/breakout', title: '打砖块', desc: '左右移动弹板, 把砖块全部击碎' },
] as const

type GameKey = (typeof games)[number]['key']

/** 三个游戏各自的最高分存档(大厅展示用) */
const bests: Record<GameKey, ReturnType<typeof useBest>> = {
  tetris: useBest('tetris'),
  snake: useBest('snake'),
  breakout: useBest('breakout'),
}
/** 取指定游戏的最高分(模板用) */
function bestOf(key: GameKey): number {
  return bests[key].best.value
}

/** 预览画布元素收集(模板函数式 ref) */
const previews = {} as Record<GameKey, HTMLCanvasElement | null>
function setPreviewRef(el: unknown, key: GameKey) {
  previews[key] = el as HTMLCanvasElement | null
}

/** 像素方块: 以 size 为格绘一个带 1px 内亮边的像素块(复古手感) */
function px(ctx: CanvasRenderingContext2D, x: number, y: number, size: number, color: string) {
  ctx.fillStyle = color
  ctx.fillRect(x, y, size, size)
  ctx.fillStyle = 'rgba(255,255,255,0.28)'
  ctx.fillRect(x, y, size, Math.max(2, size * 0.14))
}

/** 预览底: 暗绿屏幕 + 网格微光 */
function drawScreenBase(ctx: CanvasRenderingContext2D) {
  ctx.fillStyle = '#20302a'
  ctx.fillRect(0, 0, PREVIEW_W, PREVIEW_H)
  ctx.strokeStyle = 'rgba(255,255,255,0.05)'
  for (let x = 0; x <= PREVIEW_W; x += 10) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, PREVIEW_H); ctx.stroke()
  }
  for (let y = 0; y <= PREVIEW_H; y += 10) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(PREVIEW_W, y); ctx.stroke()
  }
}

/** 俄罗斯方块预览: 底部堆积 + 空中 T 块 */
function drawTetris(ctx: CanvasRenderingContext2D) {
  drawScreenBase(ctx)
  const s = 12
  const stack: [number, number, string][] = [
    [2, 7, '#5b8def'], [3, 7, '#5b8def'], [4, 7, '#e6b455'], [5, 7, '#e6b455'],
    [3, 6, '#e6b455'], [6, 6, '#67c98f'], [7, 6, '#67c98f'], [6, 7, '#67c98f'],
    [1, 7, '#e07a6a'], [1, 6, '#e07a6a'], [2, 6, '#e07a6a'],
  ]
  for (const [cx, cy, c] of stack) px(ctx, cx * s, PREVIEW_H - (cy + 1) * s, s - 1, c)
  // 空中的 T 形块
  const t: [number, number][] = [[4, 1], [5, 1], [6, 1], [5, 2]]
  for (const [cx, cy] of t) px(ctx, cx * s + s, cy * s + 10, s - 1, '#b58ae0')
}

/** 贪吃蛇预览: S 形蛇身 + 苹果 */
function drawSnake(ctx: CanvasRenderingContext2D) {
  drawScreenBase(ctx)
  const s = 12
  const body: [number, number][] = [
    [2, 2], [3, 2], [4, 2], [5, 2], [5, 3], [5, 4],
    [4, 4], [3, 4], [2, 4], [2, 5], [2, 6], [3, 6],
  ]
  body.forEach(([cx, cy], i) => {
    // 头亮尾暗, 制造渐变蛇身
    const alpha = 1 - (i / body.length) * 0.45
    ctx.globalAlpha = alpha
    px(ctx, cx * s + 6, cy * s + 6, s - 1, i === 0 ? '#a8e6b0' : '#67c98f')
    ctx.globalAlpha = 1
  })
  px(ctx, 8 * s + 6, 3 * s + 6, s - 1, '#e07a6a')
}

/** 打砖块预览: 砖阵 + 弹球 + 弹板 */
function drawBreakout(ctx: CanvasRenderingContext2D) {
  drawScreenBase(ctx)
  const rows = ['#e07a6a', '#e6b455', '#67c98f', '#5b8def']
  rows.forEach((c, r) => {
    for (let i = 0; i < 7; i++) {
      if (r === 2 && i === 4) continue // 留一个缺口显弹痕
      px(ctx, 14 + i * 25, 12 + r * 15, 22, c)
    }
  })
  ctx.beginPath()
  ctx.arc(118, 78, 4, 0, Math.PI * 2)
  ctx.fillStyle = '#f5f1e6'
  ctx.fill()
  px(ctx, 96, 92, 46, '#d8d2c2')
}

/** 首次进入: 绘制各卡带预览 */
onMounted(() => {
  const drawers: Record<GameKey, (ctx: CanvasRenderingContext2D) => void> = {
    tetris: drawTetris,
    snake: drawSnake,
    breakout: drawBreakout,
  }
  for (const g of games) {
    const canvas = previews[g.key]
    if (canvas) {
      // 画布属性按 2x 尺寸声明, 此处统一缩放为逻辑坐标绘制
      const ctx = canvas.getContext('2d')!
      ctx.setTransform(2, 0, 0, 2, 0, 0)
      drawers[g.key](ctx)
    }
  }
})
</script>
