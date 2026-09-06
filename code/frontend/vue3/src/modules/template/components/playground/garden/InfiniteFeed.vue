<template>
  <!-- 无限信息流: 哨兵元素进入视口即加载下一页, 骨架屏占位模拟延迟 -->
  <div class="flex flex-col gap-4 lg:flex-row">
    <div class="flex-1">
      <div ref="scroller" class="h-56 space-y-2 overflow-y-auto rounded-md border border-[var(--el-border-color-light)] bg-[var(--el-fill-color-light)] p-2">
        <div v-for="n in items" :key="n.id" class="flex items-center gap-3 rounded border border-[var(--el-border-color-lighter)] bg-[var(--el-bg-color)] px-3 py-2">
          <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--el-color-primary-light-8)] text-sm">{{ n.icon }}</span>
          <div class="min-w-0">
            <p class="truncate text-sm">{{ n.title }}</p>
            <p class="text-xs text-[var(--el-text-color-secondary)]">{{ n.meta }}</p>
          </div>
        </div>
        <!-- 加载骨架屏 -->
        <template v-if="loading">
          <div v-for="i in 3" :key="`sk-${i}`" class="flex items-center gap-3 rounded border border-[var(--el-border-color-lighter)] px-3 py-2" style="animation: gdn-pulse 1.2s ease-in-out infinite">
            <span class="h-8 w-8 shrink-0 rounded-full bg-[var(--el-fill-color-dark)]" />
            <div class="flex-1 space-y-1">
              <span class="block h-3 w-3/5 rounded bg-[var(--el-fill-color-dark)]" />
              <span class="block h-2.5 w-2/5 rounded bg-[var(--el-fill-color)]" />
            </div>
          </div>
        </template>
        <p v-if="!hasMore" class="py-2 text-center text-xs text-[var(--el-text-color-secondary)]">— 苗圃已见底, 没有更多了 —</p>
        <!-- 哨兵: 进入视口触发加载 -->
        <div ref="sentinel" class="h-1" />
      </div>
      <el-button size="small" class="mt-2" @click="reset">重置苗圃</el-button>
    </div>

    <!-- 说明 -->
    <div class="w-full shrink-0 space-y-1 lg:w-56">
      <p class="pt-1 text-xs leading-5 text-[var(--el-text-color-secondary)]">
        哨兵是一个 1px 高的空 div, 挂在列表末尾; IntersectionObserver 的 root 是滚动容器,
        哨兵可见即触发 loadMore —— 不需要监听 scroll 也不需要计算高度。
      </p>
      <p class="text-xs leading-5 text-[var(--el-text-color-secondary)]">
        真实场景把 setTimeout 换成接口请求, 骨架屏期间用户感知不到网络抖动。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
// 无限滚动(garden.bradwoods.io/notes/javascript/web-api/intersection-observer):
// 哨兵元素 + IntersectionObserver 的经典组合
/** 信息流条目 */
interface FeedItem {
  id: number
  title: string
  meta: string
  icon: string
}

/** 素材池 */
const ICONS = ['🌱', '🌿', '🌸', '🍄', '🦋', '🍃', '🌾', '🌻']
const TITLES = ['堆肥三问', '蚯蚓塔搭建', '雨水收集法', '伴生种植表', '香草扦插记', '堆叠花盆术', '堆冬前修剪', '种子交换日', '苔藓微景观', '堆箱翻堆指南']

/** 已加载条目 */
const items = ref<FeedItem[]>([])

/** 是否加载中 */
const loading = ref(false)

/** 是否还有更多 */
const hasMore = ref(true)

/** 自增 id */
let seq = 0

/** 滚动容器与哨兵引用 */
const scroller = ref<HTMLElement | null>(null)
const sentinel = ref<HTMLElement | null>(null)

/** 观察器实例与模拟延迟句柄 */
let io: IntersectionObserver | null = null
let timer: ReturnType<typeof setTimeout> | null = null

/** 生成一页(3条)数据 */
function makePage(): FeedItem[] {
  return Array.from({ length: 3 }, () => {
    seq += 1
    return {
      id: seq,
      title: TITLES[seq % TITLES.length],
      meta: `笔记 #${seq} · 2 分钟前`,
      icon: ICONS[seq % ICONS.length],
    }
  })
}

/** 加载下一页: 骨架屏 + 模拟网络延迟 */
function loadMore() {
  if (loading.value || !hasMore.value) return
  loading.value = true
  timer = setTimeout(() => {
    items.value.push(...makePage())
    loading.value = false
    if (items.value.length >= 33) hasMore.value = false
  }, 700)
}

/** 重置列表 */
function reset() {
  items.value = []
  seq = 0
  hasMore.value = true
}

onMounted(() => {
  io = new IntersectionObserver(
    (entries) => {
      if (entries.some((e) => e.isIntersecting)) loadMore()
    },
    { root: scroller.value, rootMargin: '80px' },
  )
  if (sentinel.value) io.observe(sentinel.value)
})

onBeforeUnmount(() => {
  io?.disconnect()
  if (timer) clearTimeout(timer)
})
</script>

<style scoped>
/* 骨架屏呼吸 */
@keyframes gdn-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.45; }
}
</style>
