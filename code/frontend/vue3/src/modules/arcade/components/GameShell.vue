<template>
  <!-- 游戏页公共壳: 顶部返回大厅 + 标题 + 分数, 主体为游戏区插槽 -->
  <div flex flex-col h-app w-full bg-note-paper overflow-hidden>
    <!-- 页头: 返回 + 标语 + 分数区 -->
    <header bg-note-gradient px-4 md:px-6 py-3 border-b border-note shrink-0>
      <div flex items-center gap-3 flex-wrap>
        <RouterLink
          to="/arcade"
          class="note-transition inline-flex items-center gap-1 rounded-lg border border-note bg-note-card px-2.5 py-1.5 text-xs font-medium text-note-sub hover:text-note-green hover:border-note-green"
          title="返回游戏大厅"
        >
          <span class="i-ep-arrow-left" text-sm />
          大厅
        </RouterLink>
        <div min-w-0>
          <h1 text-base md:text-lg font-bold text-note style="font-family: var(--note-font-hand)">
            {{ title }}
          </h1>
        </div>
        <!-- 分数区: 当前分 + 本机最高分, 由各游戏实时传入 -->
        <div ml-auto flex items-center gap-2>
          <span
            class="inline-flex items-center gap-1.5 rounded-lg border border-note bg-note-tint px-2.5 py-1 text-xs font-medium text-note"
            title="本机最高分"
          >
            <span class="i-ep-trophy" text-sm text-note-green />
            {{ best }}
          </span>
          <span
            class="inline-flex items-center gap-1.5 rounded-lg border border-note-green bg-note-tint px-2.5 py-1 text-xs font-bold text-note-green"
          >
            <span class="i-ep-star" text-sm />
            {{ score }}
          </span>
          <!-- 页面自定义状态区(如命数/关卡/下一块) -->
          <slot name="status" />
        </div>
      </div>
    </header>

    <!-- 游戏主体: 画布 / 覆盖层 / 触屏按键由页面自行填充 -->
    <main flex-1 min-h-0 flex flex-col items-center justify-center gap-3 p-3 md:p-4 overflow-auto>
      <slot />
    </main>
  </div>
</template>

<script setup lang="ts">
/** 游戏壳组件: 统一三个游戏的页面骨架, 分数仅作展示, 逻辑在各游戏页 */
defineProps<{
  /** 游戏名(页头标语) */
  title: string
  /** 当前分数 */
  score: number
  /** 本机最高分 */
  best: number
}>()
</script>
