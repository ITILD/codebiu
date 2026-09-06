<template>
  <!-- 段落节奏: 版心宽度/行高/字距/段距四大旋钮, 现场调出舒适的正文排印 -->
  <div class="flex flex-col gap-4 lg:flex-row">
    <article
      class="prose flex-1 rounded-md border border-[var(--el-border-color-light)] bg-[var(--el-fill-color-light)] p-4 text-sm"
      :style="proseStyle"
    >
      <p class="mb-2">花园笔记的价值不在辞藻，而在节奏。行长控制在 45 到 75 个字符之间，眼睛从行尾折回行首才不易串行；行高取字号的 1.5 至 1.8 倍，行与行之间便有了呼吸。</p>
      <p class="mb-2">段落之间的空隙应当大于行距、小于标题间距，让"气口"有层次。字距微调 0.02em 就能让中文方块字不再拥挤，但超过 0.1em 反而松散。</p>
      <p>排印没有唯一正确值，只有"此刻最舒服"的参数组合 —— 所以把它做成四个旋钮，随时现场调音。</p>
    </article>

    <!-- 控制面板 -->
    <div class="w-full shrink-0 space-y-1 lg:w-56">
      <div v-for="c in controls" :key="c.key" class="flex items-center gap-2">
        <span class="w-14 shrink-0 text-xs text-[var(--el-text-color-secondary)]">{{ c.label }}</span>
        <el-slider v-model="state[c.key]" :min="c.min" :max="c.max" :step="c.step ?? 1" size="small" class="flex-1" />
      </div>
      <el-button size="small" class="w-full" @click="applyBest">一键推荐值</el-button>
      <p class="pt-1 text-xs leading-5 text-[var(--el-text-color-secondary)]">
        45–75ch 版心与 1.5–1.8 行高是可读性研究的经典结论; "ch"等于数字 0 的宽度, 与字体无关地近似一个中文字符。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
// 排印四要素(garden.bradwoods.io 排版类笔记): measure/leading/tracking/paragraph spacing
import type { CSSProperties } from 'vue'

/** 滑杆配置 */
interface SliderConf {
  key: 'measure' | 'leading' | 'tracking' | 'para'
  label: string
  min: number
  max: number
  step?: number
}

/** 控制项 */
const controls: SliderConf[] = [
  { key: 'measure', label: '版心ch', min: 30, max: 75 },
  { key: 'leading', label: '行高', min: 1.4, max: 2.2, step: 0.05 },
  { key: 'tracking', label: '字距em', min: 0, max: 0.12, step: 0.005 },
  { key: 'para', label: '段距em', min: 0.4, max: 2, step: 0.1 },
]

/** 可调参数 */
const state = reactive<Record<string, number>>({ measure: 52, leading: 1.75, tracking: 0.02, para: 1 })

/** 正文样式: 四旋钮直接映射到 CSS */
const proseStyle = computed<CSSProperties>(() => ({
  maxWidth: `${state.measure}ch`,
  lineHeight: state.leading,
  letterSpacing: `${state.tracking}em`,
}))

/** 一键套用推荐值 */
function applyBest() {
  Object.assign(state, { measure: 62, leading: 1.7, tracking: 0.02, para: 0.9 })
}
</script>

<style scoped>
/* 段距旋钮通过 CSS 变量注入段落 margin */
.prose :deep(p) {
  margin-bottom: v-bind('`${state.para}em`');
}
</style>
