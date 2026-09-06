<template>
  <!-- 果汁感按钮: 挤压拉伸 + 粒子迸发 + 磁吸悬停 + 里程碑震屏 -->
  <div class="flex flex-col items-center gap-5">
    <!-- 舞台(里程碑时抖动) -->
    <div
      class="relative flex w-full items-center justify-center overflow-hidden rounded-md border border-dashed border-[var(--el-border-color)] py-10"
      :class="{ 'is-wobble': wobble }"
    >
      <button
        ref="btn"
        class="juice-btn"
        @click="pop"
        @mousemove="magnet"
        @mouseleave="unmagnet"
      >
        给我浇水
        <!-- 粒子迸发层 -->
        <span
          v-for="p in particles"
          :key="p.id"
          class="particle"
          :style="particleStyle(p)"
        />
      </button>
    </div>

    <!-- 计数与反馈 -->
    <div class="text-sm text-[var(--el-text-color-secondary)]">
      已浇水
      <span :key="count" class="pop-num">{{ count }}</span>
      次
      <span v-if="count > 0 && count % 10 === 0" class="ml-1 font-semibold text-[var(--el-color-warning)]">大丰收！</span>
    </div>
    <p class="max-w-md text-center text-xs leading-5 text-[var(--el-text-color-secondary)]">
      Juice(游戏手感): 挤压拉伸(squash & stretch)、粒子反馈、磁吸悬停与里程碑庆祝，让操作"有生命感"。
    </p>
  </div>
</template>

<script setup lang="ts">
// Juice(garden.bradwoods.io/notes/design/juice):
// 用游戏手感技巧(形变/粒子/磁吸/庆祝)增强普通按钮的操作反馈

/** 粒子 */
interface Particle {
  id: number
  x: number
  y: number
  dx: number
  dy: number
  size: number
  color: string
  delay: number
}

/** 粒子色板(取自花园主题) */
const COLORS = ['#4a7c59', '#b08a3e', '#c95f5f', '#5b8fa8', '#d8b64a', '#8a67a8']

/** 按钮引用 */
const btn = ref<HTMLButtonElement | null>(null)

/** 浇水次数 */
const count = ref(0)

/** 粒子列表 */
const particles = ref<Particle[]>([])

/** 粒子自增 id */
let pid = 0

/** 里程碑抖动开关 */
const wobble = ref(false)

/** 粒子内联样式(含 --dx/--dy 自定义属性供动画使用) */
function particleStyle(p: Particle) {
  return {
    left: `${p.x}px`,
    top: `${p.y}px`,
    width: `${p.size}px`,
    height: `${p.size}px`,
    background: p.color,
    animationDelay: `${p.delay}s`,
    '--dx': `${p.dx}px`,
    '--dy': `${p.dy}px`,
  } as Record<string, string>
}

/** 迸发一批粒子 */
function burst(x: number, y: number, n: number) {
  const born: number[] = []
  for (let k = 0; k < n; k++) {
    const a = Math.random() * Math.PI * 2
    const d = 40 + Math.random() * 70
    const id = ++pid
    born.push(id)
    particles.value.push({
      id,
      x,
      y,
      dx: Math.cos(a) * d,
      dy: Math.sin(a) * d - 30,
      size: 5 + Math.random() * 6,
      color: COLORS[k % COLORS.length],
      delay: Math.random() * 0.06,
    })
  }
  setTimeout(() => {
    particles.value = particles.value.filter((p) => !born.includes(p.id))
  }, 900)
}

/** 点击: 计数 + 挤压动画 + 粒子 + 里程碑庆祝 */
function pop(e: MouseEvent) {
  count.value++
  const el = btn.value
  if (!el) return
  const r = el.getBoundingClientRect()
  burst(e.clientX - r.left, e.clientY - r.top, count.value % 10 === 0 ? 22 : 10)
  // 重触发挤压动画: 先移除类, 强制回流, 再加回
  el.classList.remove('is-squash')
  void el.offsetWidth
  el.classList.add('is-squash')
  if (count.value % 10 === 0) {
    wobble.value = true
    setTimeout(() => (wobble.value = false), 600)
  }
}

/** 磁吸悬停: 按钮朝光标轻微偏移 */
function magnet(e: MouseEvent) {
  const el = btn.value
  if (!el) return
  const r = el.getBoundingClientRect()
  const dx = e.clientX - (r.left + r.width / 2)
  const dy = e.clientY - (r.top + r.height / 2)
  el.style.translate = `${dx * 0.18}px ${dy * 0.18}px`
}

/** 离开按钮: 复位磁吸 */
function unmagnet() {
  if (btn.value) btn.value.style.translate = ''
}
</script>

<style scoped>
/* 主按钮: 渐变底 + 悬浮投影, 按下时压扁 */
.juice-btn {
  position: relative;
  padding: 0.75rem 2.25rem;
  border-radius: 9999px;
  border: none;
  cursor: pointer;
  color: #fff;
  font-size: 1rem;
  font-weight: 600;
  letter-spacing: 0.05em;
  background: linear-gradient(135deg, var(--el-color-primary), var(--el-color-primary-dark-2));
  box-shadow: 0 6px 16px -6px var(--el-color-primary);
  transition: scale 0.2s ease;
}

.juice-btn:hover { scale: 1.03; }
.juice-btn:active { scale: 0.96; }

/* 挤压拉伸(squash & stretch): 弹性曲线 */
.juice-btn.is-squash {
  animation: juice-squash 0.4s cubic-bezier(0.22, 1.2, 0.36, 1);
}

@keyframes juice-squash {
  0% { transform: scale(1); }
  35% { transform: scale(1.12, 0.82); }
  65% { transform: scale(0.94, 1.08); }
  100% { transform: scale(1); }
}

/* 粒子: 从点击点飞散淡出 */
.particle {
  position: absolute;
  border-radius: 9999px;
  pointer-events: none;
  animation: juice-fly 0.7s ease-out forwards;
}

@keyframes juice-fly {
  to {
    transform: translate(var(--dx), var(--dy)) scale(0.15);
    opacity: 0;
  }
}

/* 计数弹跳 */
.pop-num {
  display: inline-block;
  min-width: 1.5em;
  color: var(--el-color-primary);
  font-weight: 700;
  animation: juice-pop 0.3s ease-out;
}

@keyframes juice-pop {
  0% { transform: scale(1.6); }
  100% { transform: scale(1); }
}

/* 里程碑抖动 */
.is-wobble { animation: juice-wobble 0.5s ease-in-out; }

@keyframes juice-wobble {
  0%, 100% { transform: translateX(0); }
  20% { transform: translateX(-6px) rotate(-0.4deg); }
  40% { transform: translateX(5px) rotate(0.4deg); }
  60% { transform: translateX(-3px); }
  80% { transform: translateX(2px); }
}
</style>
