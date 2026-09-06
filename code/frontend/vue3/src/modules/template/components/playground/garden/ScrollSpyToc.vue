<template>
  <!-- 滚动监听目录: IntersectionObserver rootMargin 把视口压成中线, 区块越线即高亮; 支持按类别分组 -->
  <nav aria-label="页面目录" class="flex flex-col">
    <div v-for="g in groups" :key="g.label" class="mb-1">
      <p class="mb-0.5 mt-2 pl-3 text-[11px] font-semibold uppercase tracking-widest text-[var(--el-text-color-secondary)]">{{ g.label }}</p>
      <button
        v-for="it in g.items"
        :key="it.id"
        class="group flex w-full items-center gap-2 border-l-2 py-1.5 pl-3 pr-1 text-left text-sm transition-all duration-200"
        :class="active === it.id
          ? '-ml-0.5 border-[var(--el-color-primary)] bg-[var(--el-color-primary-light-9)] pl-4 font-semibold text-[var(--el-color-primary)]'
          : 'border-transparent text-[var(--el-text-color-secondary)] hover:border-[var(--el-border-color)] hover:text-[var(--el-text-color-primary)]'"
        @click="go(it.id)"
      >
        <span
          class="h-1.5 w-1.5 shrink-0 rounded-full transition-colors"
          :class="active === it.id ? 'bg-[var(--el-color-primary)]' : 'bg-[var(--el-border-color)] group-hover:bg-[var(--el-text-color-secondary)]'"
        />
        {{ it.label }}
      </button>
    </div>
  </nav>
</template>

<script setup lang="ts">
// 目录高亮(garden.bradwoods.io/notes/javascript/web-api/intersection-observer/table-of-contents):
// rootMargin: '-45% 0px -50% 0px' 把判定区压成视口中部 1px 线, 区块穿过即触发
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import type { TocGroup } from './types'

/** 目录分组 */
const props = defineProps<{ groups: TocGroup[] }>()

/** 展平的全部条目(观察用) */
const flatItems = computed(() => props.groups.flatMap((g) => g.items))

/** 当前高亮条目 id */
const active = ref(flatItems.value[0]?.id ?? '')

/** 观察器实例 */
let io: IntersectionObserver | null = null

onMounted(() => {
  io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (e.isIntersecting) active.value = e.target.id
      }
    },
    // 视口上下各收 45%/50%, 剩下中部一条细线
    { rootMargin: '-45% 0px -50% 0px', threshold: 0 },
  )
  for (const it of flatItems.value) {
    const el = document.getElementById(it.id)
    if (el) io.observe(el)
  }
})

onBeforeUnmount(() => io?.disconnect())

/** 点击目录: 平滑滚动到区块 */
function go(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
</script>
