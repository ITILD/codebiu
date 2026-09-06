<template>
  <!-- 视图过渡画廊: 缩略图与大图共享 view-transition-name, 点击时元素平滑变形换位 -->
  <div ref="rootEl">
    <!-- 大图区: 选中时携带过渡名(与被点缩略图配对变形) -->
    <div
      ref="featured"
      class="relative mb-4 flex items-center justify-center overflow-hidden rounded-md border border-[var(--el-border-color-light)] bg-[var(--el-fill-color-light)]"
      :style="featuredCss"
    >
      <img
        v-if="selected !== null"
        :src="photos[selected].src"
        :alt="photos[selected].title"
        decoding="async"
        class="aspect-video w-full object-cover md:aspect-[16/7]"
      >
      <span v-else class="p-6 text-sm text-[var(--el-text-color-secondary)]">点击下方图片，缩略图将平滑"变形"放大到此处</span>
      <template v-if="selected !== null">
        <el-button class="absolute right-2 top-2" size="small" @click="close">收起</el-button>
        <div class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/60 to-transparent px-3 pb-2 pt-6 text-sm text-white">
          {{ photos[selected].title }}
        </div>
      </template>
    </div>

    <!-- 缩略图网格 -->
    <div class="grid grid-cols-3 gap-3 md:grid-cols-6">
      <button
        v-for="(p, i) in photos"
        :key="p.src"
        :data-thumb="i"
        class="group relative overflow-hidden rounded-md border-2 transition-colors"
        :class="selected === i
          ? 'border-[var(--el-color-primary)]'
          : 'border-transparent hover:border-[var(--el-color-primary-light-5)]'"
        @click="open(i, $event)"
      >
        <img :src="p.src" :alt="p.title" loading="lazy" decoding="async" class="aspect-square w-full object-cover">
      </button>
    </div>

    <p class="mt-3 text-xs leading-5 text-[var(--el-text-color-secondary)]">
      原理: 点击时临时给缩略图设置 view-transition-name，document.startViewTransition 捕获前后两帧，
      同名元素之间自动补间变形；过渡结束后归还名字。{{ supportsVT ? '' : '(当前浏览器不支持该 API，退化为直接切换)' }}
    </p>
  </div>
</template>

<script setup lang="ts">
// View Transition API(garden.bradwoods.io/notes/javascript/web-api/view-transition):
// 同文档过渡 + 共享元素(view-transition-name)变形, 缩略图 ↔ 大图双向 morph
import { galleryPhotos } from './texture'

/** 共享元素过渡名(同一时刻只允许一个元素持有) */
const VT_NAME = 'garden-photo'

/** 画廊配图 */
const photos = galleryPhotos

/** 根容器(供查询缩略图) */
const rootEl = ref<HTMLElement | null>(null)

/** 大图容器 */
const featured = ref<HTMLElement | null>(null)

/** 当前选中索引 */
const selected = ref<number | null>(null)

/** 过渡进行中(防连点) */
const busy = ref(false)

/** 浏览器是否支持 View Transition API */
const supportsVT = typeof document.startViewTransition === 'function'

/** 大图过渡名样式(字符串形式, 挂到 style 上) */
const featuredCss = computed(() => `view-transition-name: ${selected.value !== null ? VT_NAME : 'none'}`)

/**
 * 执行一次过渡换帧
 * @param apply 新状态提交(内部需等待 DOM 更新)
 * @param before 捕获前的瞬时准备(保证捕获帧只有一个元素持有过渡名)
 * @param cleanup 过渡结束后的清理
 */
async function swap(apply: () => Promise<void>, before?: () => void, cleanup?: () => void) {
  if (!document.startViewTransition) {
    await apply()
    return
  }
  busy.value = true
  before?.()
  const vt = document.startViewTransition(apply)
  try {
    await vt.finished
  } finally {
    cleanup?.()
    busy.value = false
  }
}

/** 打开图片: 缩略图 → 大图变形 */
async function open(i: number, e: MouseEvent) {
  if (busy.value || selected.value === i) return
  const thumb = (e.currentTarget as HTMLElement) ?? null
  const prev = selected.value
  await swap(
    async () => {
      selected.value = i
      await nextTick()
      thumb?.style.removeProperty('view-transition-name')
      featured.value?.style.setProperty('view-transition-name', VT_NAME)
    },
    () => {
      thumb?.style.setProperty('view-transition-name', VT_NAME)
      if (prev !== null) featured.value?.style.setProperty('view-transition-name', 'none')
    },
  )
}

/** 收起大图: 大图 → 缩略图反向变形 */
async function close() {
  if (busy.value || selected.value === null) return
  const idx = selected.value
  const thumb = rootEl.value?.querySelector<HTMLElement>(`[data-thumb="${idx}"]`) ?? null
  await swap(
    async () => {
      selected.value = null
      await nextTick()
      thumb?.style.setProperty('view-transition-name', VT_NAME)
    },
    undefined,
    () => thumb?.style.removeProperty('view-transition-name'),
  )
}
</script>

<style>
/* 过渡伪元素挂在文档根节点, 必须用全局样式 */
::view-transition-old(garden-photo),
::view-transition-new(garden-photo) {
  animation-duration: 0.45s;
}
</style>
