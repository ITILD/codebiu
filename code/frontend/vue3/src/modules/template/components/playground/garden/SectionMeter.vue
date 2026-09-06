<template>
  <!-- 区块计量: IntersectionObserver 记录"看过的"区块, 计量条随之点亮 -->
  <div class="flex flex-col gap-4 lg:flex-row">
    <div class="flex-1 space-y-2">
      <div class="flex items-center gap-2">
        <span class="text-xs text-[var(--el-text-color-secondary)]">已探索 {{ visited.size }} / {{ zones.length }} 区</span>
        <div class="relative h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--el-fill-color-dark)]">
          <div
            class="h-full bg-[var(--el-color-primary)] transition-all duration-300"
            :style="{ width: `${(visited.size / zones.length) * 100}%` }"
          />
        </div>
      </div>
      <!-- 滚动区: 每个季节是一个"观察区" -->
      <div ref="scroller" class="h-52 space-y-2 overflow-y-auto rounded-md border border-[var(--el-border-color-light)] p-2">
        <div
          v-for="z in zones"
          :key="z.name"
          class="flex h-24 items-center justify-between rounded border px-4 transition-colors duration-300"
          :class="visited.has(z.name) ? 'border-[var(--el-color-primary)] bg-[var(--el-color-primary-light-9)]' : 'border-[var(--el-border-color-light)] bg-[var(--el-fill-color-light)]'"
        >
          <span class="text-sm font-semibold">{{ z.name }}</span>
          <span class="text-xs text-[var(--el-text-color-secondary)]">{{ z.tip }}</span>
        </div>
      </div>
    </div>

    <!-- 说明 -->
    <div class="w-full shrink-0 space-y-1 lg:w-56">
      <p class="pt-1 text-xs leading-5 text-[var(--el-text-color-secondary)]">
        threshold 0.6 表示区块 60% 进入视口才算"到访"; visited 是 Set, 只增不减 ——
        计量的是"探索进度"而非"当前位置", 与 ScrollSpyToc 的高亮逻辑是两种意图。
      </p>
      <p class="text-xs leading-5 text-[var(--el-text-color-secondary)]">
        适合新手引导(看过的步骤打勾)、课程章节完成度等场景。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
// 区块到访计量(garden.bradwoods.io/notes/javascript/web-api/intersection-observer)
/** 观察区定义 */
interface Zone {
  name: string
  tip: string
}

/** 四季区块 */
const zones: Zone[] = [
  { name: '春 · 萌发', tip: 'threshold 0.6 触发' },
  { name: '夏 · 盛放', tip: 'root = 滚动容器' },
  { name: '秋 · 结果', tip: '只记录首次到访' },
  { name: '冬 · 蓄力', tip: 'Set 记录不回退' },
]

/** 已到访区块名集合 */
const visited = reactive(new Set<string>())

/** 滚动容器引用 */
const scroller = ref<HTMLElement | null>(null)

/** 观察器实例 */
let io: IntersectionObserver | null = null

onMounted(() => {
  io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (e.isIntersecting) visited.add((e.target as HTMLElement).dataset.zone ?? '')
      }
    },
    // 以滚动容器为 root, 区块 60% 可见即算到访
    { root: scroller.value, threshold: 0.6 },
  )
  scroller.value?.querySelectorAll<HTMLElement>('[data-zone]').forEach((el) => io?.observe(el))
})

onBeforeUnmount(() => io?.disconnect())
</script>
