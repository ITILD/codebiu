<template>
  <!-- 滑动分页: CSS scroll-snap 完成吸附, JS 只负责把滚动位置换算成页码 -->
  <div class="flex flex-col gap-4 lg:flex-row">
    <div class="flex-1">
      <!-- 横向滚动容器: snap-x mandatory 让每页吸附对齐 -->
      <div ref="track" class="pager flex h-56 snap-x snap-mandatory gap-3 overflow-x-auto rounded-md border border-[var(--el-border-color-light)] bg-[var(--el-fill-color-light)] p-3" @scroll.passive="onScroll">
        <figure
          v-for="p in photos"
          :key="p.title"
          class="relative h-full w-4/5 shrink-0 snap-center overflow-hidden rounded-md sm:w-1/2"
        >
          <img :src="p.src" :alt="p.title" class="h-full w-full object-cover" loading="lazy" decoding="async" />
          <figcaption class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/60 to-transparent px-3 py-2 text-sm text-white">{{ p.title }}</figcaption>
        </figure>
      </div>
      <!-- 页码圆点 -->
      <div class="mt-2 flex items-center justify-center gap-2">
        <button
          v-for="(p, i) in photos"
          :key="i"
          class="h-2 rounded-full transition-all duration-300"
          :class="active === i ? 'w-6 bg-[var(--el-color-primary)]' : 'w-2 bg-[var(--el-border-color-darker)] hover:bg-[var(--el-text-color-secondary)]'"
          :aria-label="`第 ${i + 1} 页: ${p.title}`"
          @click="go(i)"
        />
      </div>
    </div>

    <!-- 说明 -->
    <div class="w-full shrink-0 space-y-1 lg:w-56">
      <p class="pt-1 text-xs leading-5 text-[var(--el-text-color-secondary)]">
        scroll-snap-type: x mandatory + 子项 scroll-snap-align: center, 两行声明完成"翻页吸附";
        JS 侧只是监听 scroll, 用 round(scrollLeft / 页宽) 同步圆点, 点击圆点再 scrollIntoView 回写。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
// scroll-snap 分页(garden.bradwoods.io CSS 笔记): 吸附交给 CSS, 状态同步交给少量 JS
import { galleryPhotos } from './texture'

/** 演示图片 */
const photos = galleryPhotos.slice(0, 5)

/** 当前页索引 */
const active = ref(0)

/** 轨道引用 */
const track = ref<HTMLElement | null>(null)

/** rAF 合帧句柄 */
let raf = 0

/** 页宽近似(首项宽度 + gap) */
function pageWidth(): number {
  const el = track.value
  if (!el) return 1
  const first = el.firstElementChild as HTMLElement | null
  return (first?.offsetWidth ?? el.clientWidth) + 12
}

/** 滚动: 换算当前页码 */
function onScroll() {
  cancelAnimationFrame(raf)
  raf = requestAnimationFrame(() => {
    const el = track.value
    if (!el) return
    active.value = Math.min(photos.length - 1, Math.round(el.scrollLeft / pageWidth()))
  })
}

/** 点击圆点: 平滑滚动到对应页 */
function go(i: number) {
  track.value?.scrollTo({ left: i * pageWidth(), behavior: 'smooth' })
}

onBeforeUnmount(() => cancelAnimationFrame(raf))
</script>
