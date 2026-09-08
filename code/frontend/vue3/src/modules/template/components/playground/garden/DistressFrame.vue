<template>
  <!-- 蚀刻斑驳: feTurbulence 生成噪声, feComponentTransfer 阈值化 alpha, feComposite 只保留噪声覆盖处 -->
  <div class="flex flex-col gap-4 lg:flex-row">
    <div class="relative flex flex-1 items-center justify-center overflow-hidden rounded-md border border-[var(--el-border-color-light)] bg-[var(--el-bg-color-page)] py-10">
      <svg width="0" height="0" class="absolute" aria-hidden="true">
        <defs>
          <!-- x/y/width/height 必须用百分比: 无单位数值按 objectBoundingBox 倍数解析, -10 会把滤镜区域推到元素外导致整体不可见 -->
          <filter id="gdn-distress" x="-10%" y="-10%" width="120%" height="120%">
            <feTurbulence type="fractalNoise" :baseFrequency="state.freq" numOctaves="3" result="noise" />
            <feComponentTransfer in="noise" result="mask">
              <feFuncA type="discrete" :tableValues="tableValues" />
            </feComponentTransfer>
            <feComposite in="SourceGraphic" in2="mask" operator="in" />
          </filter>
        </defs>
      </svg>
      <!-- 被蚀刻的铭文 -->
      <div class="px-6 text-center" style="filter: url(#gdn-distress)">
        <p class="font-serif text-4xl font-bold tracking-[0.3em] text-[var(--el-color-primary)]">GARDEN</p>
        <p class="mt-2 font-serif text-sm tracking-[0.5em] text-[var(--el-text-color-regular)]">EST. 2026</p>
      </div>
      <span class="pointer-events-none absolute bottom-2 left-3 text-xs text-[var(--el-text-color-secondary)]">降低完整度, 字会被噪声"啃"掉</span>
    </div>

    <!-- 控制面板 -->
    <div class="w-full shrink-0 space-y-3 lg:w-56">
      <div class="flex items-center gap-2">
        <span class="w-14 shrink-0 text-xs text-[var(--el-text-color-secondary)]">颗粒</span>
        <el-slider v-model="state.freq" :min="0.01" :max="0.12" :step="0.005" size="small" class="flex-1" />
      </div>
      <div class="flex items-center gap-2">
        <span class="w-14 shrink-0 text-xs text-[var(--el-text-color-secondary)]">完整度</span>
        <el-slider v-model="state.keep" :min="1" :max="10" size="small" class="flex-1" />
      </div>
      <p class="text-xs leading-5 text-[var(--el-text-color-secondary)]">
        原理(feTurbulence + feFuncA + feComposite): 噪声的 alpha 被 discrete 函数切成 0/1 阈值,
        feComposite operator="in" 只让源图形在"通过阈值"的像素处显示, 得到海报腐蚀质感。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
// Distress 示例(garden.bradwoods.io/notes/svg/filters#distress):
// feTurbulence 造纹理 → feComponentTransfer(feFuncA) 阈值化 → feComposite(in) 蚀刻源图形

/** 可调参数(keep 越大阈值越低, 图形越完整) */
const state = reactive({ freq: 0.05, keep: 3 })

/** discrete 阈值表: 首位 0 挡住低 alpha 噪声, 后续 1 放行; 档位越多, 通过的像素越多, 图形越完整 */
const tableValues = computed(() => `0 ${'1 '.repeat(Math.round(state.keep)).trim()}`)
</script>
