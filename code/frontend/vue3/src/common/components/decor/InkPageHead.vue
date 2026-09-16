<template>
  <!-- 水墨页头: serif 标题 + 朱砂闲章 + 淡墨晕染底纹 + 枯笔分隔线(garden 技法本地化) -->
  <header relative mb-5>
    <!-- 淡墨晕染: 外扩一点, 模拟墨在宣纸上洇开 -->
    <div class="ink-wash" absolute -inset-x-3 -top-4 -bottom-1 pointer-events-none aria-hidden="true" />

    <div relative flex flex-wrap items-end justify-between gap-x-4 gap-y-2>
      <div min-w-0>
        <h1 flex flex-wrap items-center gap-x-2.5 gap-y-1 font-serif text-xl md:text-2xl font-bold text-note leading-tight>
          {{ title }}
          <span v-if="seal" class="note-seal" :title="sealTitle || title">{{ seal }}</span>
        </h1>
        <p v-if="sub || $slots.sub" mt-1.5 text-xs md:text-sm text-note-sub leading-relaxed>
          <slot name="sub">{{ sub }}</slot>
        </p>
      </div>

      <!-- 右侧操作区(开关/按钮/链接等) -->
      <div v-if="$slots.actions" flex flex-wrap items-center gap-2 pb-0.5>
        <slot name="actions" />
      </div>
    </div>

    <!-- 枯笔飞白分隔线(feTurbulence 置换笔触, 颜色随明暗自适应) -->
    <div class="ink-divider" mt-2.5 aria-hidden="true" />
  </header>
</template>

<script setup lang="ts">
// 页面标题头(自然笔记 · 水墨风): 统一 CRUD/工具页的页头观感
// 亮暗自适应: 全部取值来自 base.css 的 --note-* 变量, 无硬编码色
// 注意: 自定义类(ink-wash/ink-divider/note-seal)必须写进 class="", 裸属性不会被 attributify 转换
withDefaults(defineProps<{
  /** 页面标题 */
  title: string
  /** 标题下描述文案(可用 #sub 插槽替代) */
  sub?: string
  /** 朱砂闲章单字(如 憩/员/枝), 不传则不显示 */
  seal?: string
  /** 闲章 title 提示, 默认用页面标题 */
  sealTitle?: string
}>(), {})
</script>
