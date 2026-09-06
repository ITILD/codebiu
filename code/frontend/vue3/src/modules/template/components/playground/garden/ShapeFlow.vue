<template>
  <!-- 文字环绕: shape-outside 让文字沿着浮动图形的真实轮廓排布, 而不只是矩形框 -->
  <div class="flex flex-col gap-4 lg:flex-row">
    <article class="prose flex-1 rounded-md border border-[var(--el-border-color-light)] bg-[var(--el-fill-color-light)] p-4 text-sm leading-7">
      <!-- 浮动图: clip-path 裁形, shape-outside 用同一形状约束文字 -->
      <img
        :src="potPhoto"
        alt="园艺静物"
        class="float-left mr-4 mb-1 object-cover"
        :style="shapeStyle"
        loading="lazy"
        decoding="async"
      />
      <p class="mb-2">清晨的温室里，黄铜喷壶与陶土花盆在木桌上静静休憩。阳光从玻璃顶斜落，把金属的冷光烘成暖金色，空气里有湿润的泥土气息。</p>
      <p class="mb-2">园丁的习惯是从左到右巡视每一株植物：先看叶背有没有蚜虫，再以指节叩一叩盆壁判断干湿，最后才提壶浇水。水要沿盆沿缓缓注入，让根系自己决定喝多少。</p>
      <p class="mb-2">shape-outside 的妙处在于：文字不再撞上一堵矩形墙，而是贴着圆形或叶形的曲线流动，像溪水绕过卵石。裁剪与排布用同一个 polygon/圆值，就得到严丝合缝的环绕。</p>
      <p> 若把图形放大，文字会被挤成更窄的溪流；缩小则恢复平原。排版因此有了"地形"。</p>
    </article>

    <!-- 控制面板 -->
    <div class="w-full shrink-0 space-y-2 lg:w-56">
      <el-segmented v-model="state.shape" :options="shapeOptions" size="small" class="w-full" />
      <div class="flex items-center gap-2">
        <span class="w-14 shrink-0 text-xs text-[var(--el-text-color-secondary)]">图宽px</span>
        <el-slider v-model="state.size" :min="90" :max="200" size="small" class="flex-1" />
      </div>
      <p class="pt-1 text-xs leading-5 text-[var(--el-text-color-secondary)]">
        shape-outside 只对浮动元素生效; 传 circle() 或与 clip-path 相同的 polygon(),
        文字便沿轮廓绕行。注意它改变的是"文字可占区域", 不裁剪图像本身, 所以两者要成对使用。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
// 文字环绕排版(garden.bradwoods.io/notes/css/floating-image):
// float + clip-path + shape-outside 三件套
import type { CSSProperties } from 'vue'
import { potPhoto } from './texture'

/** 图形档位 */
type FlowShape = 'circle' | 'leaf' | 'none'

/** 可调参数 */
const state = reactive<{ shape: FlowShape; size: number }>({ shape: 'circle', size: 140 })

/** 选项 */
const shapeOptions = [
  { label: '圆形', value: 'circle' },
  { label: '叶形', value: 'leaf' },
  { label: '矩形', value: 'none' },
]

/** 叶形多边形(裁剪与环绕共用) */
const LEAF = 'polygon(6% 40%, 50% 0%, 94% 40%, 94% 78%, 50% 100%, 6% 78%)'

/** 浮动图样式: 裁剪形状 + 环绕形状成对出现 */
const shapeStyle = computed<CSSProperties>(() => {
  const base: CSSProperties = { width: `${state.size}px`, height: `${state.size}px` }
  if (state.shape === 'circle') {
    return { ...base, clipPath: 'circle(48% at 50% 50%)', shapeOutside: 'circle(48% at 50% 50%)', borderRadius: '4px' }
  }
  if (state.shape === 'leaf') {
    return { ...base, clipPath: LEAF, shapeOutside: LEAF }
  }
  return base
})
</script>
