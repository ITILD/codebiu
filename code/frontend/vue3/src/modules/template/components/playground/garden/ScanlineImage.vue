<template>
  <!-- 扫描线: repeating-linear-gradient 叠层以 overlay 混合加到图像上 -->
  <div class="flex flex-col gap-4 lg:flex-row lg:items-center">
    <div class="relative isolate flex-1 overflow-hidden rounded-md border border-[var(--el-border-color-light)]">
      <img :src="src" alt="扫描线演示图" loading="lazy" decoding="async" class="block w-full">
      <!-- 重复渐变线: 亮底更亮、暗底更暗 -->
      <div
        class="pointer-events-none absolute inset-0"
        :style="{
          background: `repeating-linear-gradient(${angle}deg, transparent 0, ${lineColor} calc(${line}px / 2), transparent ${line}px)`,
          mixBlendMode: 'overlay',
        }"
      />
    </div>

    <!-- 控制面板 -->
    <div class="w-full shrink-0 space-y-3 lg:w-56">
      <div class="flex items-center gap-2">
        <span class="w-16 shrink-0 text-xs text-[var(--el-text-color-secondary)]">线宽</span>
        <el-slider v-model="line" :min="2" :max="16" size="small" class="flex-1" />
      </div>
      <div class="flex items-center gap-2">
        <span class="w-16 shrink-0 text-xs text-[var(--el-text-color-secondary)]">线向</span>
        <el-select v-model="angle" size="small" class="flex-1">
          <el-option v-for="a in angles" :key="a.value" :label="a.label" :value="a.value" />
        </el-select>
      </div>
      <div class="flex items-center gap-2">
        <span class="w-16 shrink-0 text-xs text-[var(--el-text-color-secondary)]">强度</span>
        <el-slider v-model="strength" :min="0" :max="1" :step="0.05" size="small" class="flex-1" />
      </div>
      <el-checkbox v-model="inverted" size="small">反相(白线提亮)</el-checkbox>
      <p class="text-xs leading-5 text-[var(--el-text-color-secondary)]">
        overlay 混合下，黑线让暗部更暗、白线让亮部更亮，即得 CRT 老电视般的扫描线质感。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
// 扫描线(garden.bradwoods.io/notes/css/blend-modes#scan-lines):
// repeating-linear-gradient + mix-blend-mode: overlay, 可调线宽/角度/强度/反相
import { mainPhoto } from './texture'

/** 可传入自定义底图 */
withDefaults(defineProps<{ src?: string }>(), { src: () => mainPhoto })

/** 线宽(px) */
const line = ref(4)

/** 线向(角度) */
const angle = ref(180)

/** 线向选项 */
const angles = [
  { label: '水平 180°', value: 180 },
  { label: '垂直 90°', value: 90 },
  { label: '斜向 45°', value: 45 },
  { label: '斜向 135°', value: 135 },
]

/** 线强度(0~1) */
const strength = ref(1)

/** 是否反相为白线 */
const inverted = ref(false)

/** 线颜色(黑线压暗 / 白线提亮) */
const lineColor = computed(() => (inverted.value ? `hsla(0, 0%, 100%, ${strength.value})` : `hsla(0, 0%, 0%, ${strength.value})`))
</script>
