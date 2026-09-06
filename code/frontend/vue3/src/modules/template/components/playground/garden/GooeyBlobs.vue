<template>
  <!-- 果冻融合球: 高斯模糊把球缘糊开, feColorMatrix 再把 alpha 陡化, 靠近的球"融合" -->
  <div class="flex flex-col gap-4 lg:flex-row">
    <div
      class="goo-stage relative isolate h-64 flex-1 overflow-hidden rounded-md border border-[var(--el-border-color-light)] bg-[var(--el-fill-color-light)]"
      @mousemove="onMove"
    >
      <!-- 滤镜定义(零尺寸 SVG, 仅作 defs) -->
      <svg width="0" height="0" class="absolute" aria-hidden="true">
        <defs>
          <filter id="gdn-gooey">
            <feGaussianBlur in="SourceGraphic" :stdDeviation="state.blur" result="blur" />
            <feColorMatrix
              in="blur"
              mode="matrix"
              :values="`1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 ${state.contrast} -${(state.contrast / 2 - 4).toFixed(1)}`"
              result="goo"
            />
            <feBlend in="SourceGraphic" in2="goo" />
          </filter>
        </defs>
      </svg>

      <!-- 球群: 滤镜作用于整个舞台 -->
      <div class="absolute inset-0" style="filter: url(#gdn-gooey)">
        <span
          v-for="b in balls"
          :key="b.id"
          class="goo-ball absolute rounded-full"
          :style="{ left: `${b.x}%`, top: `${b.y}%`, width: `${b.size}px`, height: `${b.size}px`, background: b.color, animationDuration: `${b.dur}s`, animationDelay: `${b.delay}s` }"
        />
        <!-- 鼠标球: 跟随光标, 与漂浮球融合 -->
        <span
          class="goo-ball absolute h-12 w-12 rounded-full"
          :style="{ left: `${mouse.x}%`, top: `${mouse.y}%`, background: 'var(--el-color-primary)' }"
        />
      </div>
      <span class="pointer-events-none absolute bottom-2 left-3 text-xs text-[var(--el-text-color-secondary)]">移动鼠标, 球会被"粘"住</span>
    </div>

    <!-- 控制面板 -->
    <div class="w-full shrink-0 space-y-1 lg:w-56">
      <div v-for="c in controls" :key="c.key" class="flex items-center gap-2">
        <span class="w-14 shrink-0 text-xs text-[var(--el-text-color-secondary)]">{{ c.label }}</span>
        <el-slider v-model="state[c.key]" :min="c.min" :max="c.max" :step="c.step ?? 1" size="small" class="flex-1" />
      </div>
      <p class="pt-1 text-xs leading-5 text-[var(--el-text-color-secondary)]">
        滤镜像一台机器: feGaussianBlur 先把图形糊开, feColorMatrix 把 alpha 通道陡化(对比拉满),
        靠近的模糊边缘一起越过阈值, 看起来就像融为一体的果冻。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
// SVG 滤镜(garden.bradwoods.io/notes/svg/filters):
// 多个 primitive 串联(feGaussianBlur → feColorMatrix → feBlend), 前一个的 result 作为下一个的 in
import type { CSSProperties } from 'vue'

/** 滑杆配置 */
interface SliderConf {
  key: 'blur' | 'contrast'
  label: string
  min: number
  max: number
  step?: number
}

/** 控制项 */
const controls: SliderConf[] = [
  { key: 'blur', label: '糊化', min: 4, max: 24 },
  { key: 'contrast', label: '融合', min: 12, max: 40 },
]

/** 可调参数 */
const state = reactive<Record<string, number>>({ blur: 12, contrast: 22 })

/** 漂浮球 */
const balls = Array.from({ length: 5 }, (_, i) => ({
  id: i,
  x: 12 + (i % 3) * 30 + Math.random() * 8,
  y: 18 + Math.floor(i / 3) * 42 + Math.random() * 10,
  size: 34 + (i % 3) * 14,
  color: ['#4a7c59', '#6f9579', '#93b39b', '#b08a3e', '#4a7c59'][i],
  dur: 4 + Math.random() * 3,
  delay: Math.random() * 2,
}))

/** 鼠标球位置(百分比) */
const mouse = reactive({ x: 50, y: 50 })

/** 鼠标移动: 更新跟随球位置 */
function onMove(e: MouseEvent) {
  const el = e.currentTarget as HTMLElement
  const r = el.getBoundingClientRect()
  mouse.x = ((e.clientX - r.left) / r.width) * 100
  mouse.y = ((e.clientY - r.top) / r.height) * 100
}

// 球的漂浮动画在 scoped style 中定义; 样式对象仅用于示例说明
const _unused: CSSProperties = {}
void _unused
</script>

<style scoped>
/* 漂浮球: 各自不同时长往返漂浮 */
.goo-ball {
  animation: goo-drift 5s ease-in-out infinite alternate;
}

@keyframes goo-drift {
  from { transform: translate(-14px, -10px); }
  to { transform: translate(14px, 12px); }
}
</style>
