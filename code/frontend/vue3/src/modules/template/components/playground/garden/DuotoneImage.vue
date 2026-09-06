<template>
  <!-- 双色调图像: 灰度底图 + screen 亮色层 + multiply 暗色层 -->
  <div class="flex flex-col gap-4 lg:flex-row lg:items-center">
    <div class="relative isolate flex-1 overflow-hidden rounded-md border border-[var(--el-border-color-light)]">
      <img
        :src="src"
        alt="双色调演示图"
        loading="lazy"
        decoding="async"
        class="block w-full"
        :style="{ filter: on ? `grayscale(1) brightness(${brightness}%)` : 'none' }"
      >
      <!-- screen: 取亮部染上亮色 -->
      <div
        v-if="on"
        class="pointer-events-none absolute inset-0"
        :style="{ background: lightColor, mixBlendMode: 'screen' }"
      />
      <!-- multiply: 取暗部染上暗色 -->
      <div
        v-if="on"
        class="pointer-events-none absolute inset-0"
        :style="{ background: darkColor, mixBlendMode: 'multiply' }"
      />
    </div>

    <!-- 控制面板 -->
    <div class="w-full shrink-0 space-y-3 lg:w-56">
      <el-checkbox v-model="on" size="small">启用双色调</el-checkbox>
      <div class="flex items-center gap-2">
        <span class="w-20 shrink-0 text-xs text-[var(--el-text-color-secondary)]">亮部 screen</span>
        <el-color-picker v-model="lightColor" size="small" />
        <span class="text-xs text-[var(--el-text-color-secondary)]">{{ lightColor }}</span>
      </div>
      <div class="flex items-center gap-2">
        <span class="w-20 shrink-0 text-xs text-[var(--el-text-color-secondary)]">暗部 multiply</span>
        <el-color-picker v-model="darkColor" size="small" />
        <span class="text-xs text-[var(--el-text-color-secondary)]">{{ darkColor }}</span>
      </div>
      <div class="flex items-center gap-2">
        <span class="w-20 shrink-0 text-xs text-[var(--el-text-color-secondary)]">底图亮度</span>
        <el-slider v-model="brightness" :min="60" :max="140" size="small" class="flex-1" />
      </div>
      <p class="text-xs leading-5 text-[var(--el-text-color-secondary)]">
        先把图片灰度化，screen 用亮色替换高光、multiply 用暗色替换阴影，即得复古双色印刷效果。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
// 双色调(garden.bradwoods.io/notes/css/blend-modes#duotone):
// grayscale 底图上叠加 screen(亮色)与 multiply(暗色)两个混合层
import { mainPhoto } from './texture'

/** 可传入自定义底图 */
withDefaults(defineProps<{ src?: string }>(), { src: () => mainPhoto })

/** 是否启用双色调 */
const on = ref(true)

/** 亮部色(screen 层) */
const lightColor = ref('#3d6bff')

/** 暗部色(multiply 层) */
const darkColor = ref('#e86aa6')

/** 底图亮度(%) */
const brightness = ref(110)
</script>
