<template>
  <!-- 首字下沉: 浮动放大首字母, 古典书籍排版的招牌技巧 -->
  <div class="flex flex-col gap-4 lg:flex-row">
    <article
      class="prose flex-1 rounded-md border border-[var(--el-border-color-light)] bg-[var(--el-fill-color-light)] p-4 text-sm"
      :style="{ lineHeight: `${state.lineHeight}` }"
    >
      <p class="mb-2 text-justify">
        <span v-if="state.on" class="drop-cap" :style="capStyle">园</span>
        艺是最古老的慢艺术：你把一粒种子交给时间，然后日复一日地观察、等待、修正。没有立竿见影的回报，却处处是不动声色的惊喜——第一片真叶、第一个花苞、第一只来访的蜜蜂。
      </p>
      <p class="mb-2 text-justify">
        古籍排版同样信奉"慢"的美学：章节之首放大数倍的首字母沉入两三行文字之间，读者的目光被它稳稳接住，再顺着行间滑入正文。这个技巧只需要一个浮动 span。
      </p>
      <p class="text-justify">
        CSS 也提供了更语义化的 initial-letter 属性，可惜浏览器支持尚未普及；在那之前，float + font-size + line-height 的组合就是最稳的替代方案。
      </p>
    </article>

    <!-- 控制面板 -->
    <div class="w-full shrink-0 space-y-1 lg:w-56">
      <div class="flex items-center justify-between">
        <span class="text-xs text-[var(--el-text-color-secondary)]">启用首字下沉</span>
        <el-switch v-model="state.on" size="small" />
      </div>
      <div class="flex items-center gap-2">
        <span class="w-14 shrink-0 text-xs text-[var(--el-text-color-secondary)]">字倍</span>
        <el-slider v-model="state.em" :min="2" :max="4.5" :step="0.1" size="small" class="flex-1" />
      </div>
      <div class="flex items-center gap-2">
        <span class="w-14 shrink-0 text-xs text-[var(--el-text-color-secondary)]">行高</span>
        <el-slider v-model="state.lineHeight" :min="1.4" :max="2.2" :step="0.05" size="small" class="flex-1" />
      </div>
      <p class="pt-1 text-xs leading-5 text-[var(--el-text-color-secondary)]">
        首字 float 左浮后, 后续文字环绕下沉字符排列; font-size 放大 n 倍时 line-height 需同步压缩,
        否则首字会占据 n 行高的空白 —— 调节滑杆观察两者如何博弈。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
// 首字下沉(garden.bradwoods.io 排版类笔记): float 首字方案, 兼容性优于 initial-letter
import type { CSSProperties } from 'vue'

/** 可调参数 */
const state = reactive({ on: true, em: 3, lineHeight: 1.8 })

/** 首字样式: 字号随滑杆, 行高压到 0.8 才能贴合两行文字 */
const capStyle = computed<CSSProperties>(() => ({
  fontSize: `${state.em}em`,
  lineHeight: '0.8',
}))
</script>

<style scoped>
/* 首字下沉: 衬线体 + 主题色 + 右下留白 */
.drop-cap {
  float: left;
  margin: 0.08em 0.14em 0 0;
  padding: 0.06em 0.12em;
  font-family: Georgia, 'Noto Serif SC', serif;
  font-weight: 700;
  color: var(--el-color-primary);
  border: 1px solid var(--el-border-color);
  border-radius: 3px;
  background: var(--el-color-primary-light-9);
}
</style>
