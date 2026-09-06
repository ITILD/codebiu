<template>
  <!-- 透视平移: 横向滚动时按卡片与中心的距离施加 rotateY, 形成封面流 -->
  <div class="flex flex-col gap-4 lg:flex-row">
    <div class="flex-1">
      <div ref="track" class="pan-track flex h-56 items-center gap-4 overflow-x-auto rounded-md border border-[var(--el-border-color-light)] bg-[var(--el-fill-color-light)] px-[20%]" @scroll.passive="onScroll">
        <div
          v-for="(p, i) in cards"
          :key="p.title"
          class="pan-card relative h-44 w-32 shrink-0 overflow-hidden rounded-md shadow-lg"
          :style="cardStyle(i)"
        >
          <img :src="p.src" :alt="p.title" class="h-full w-full object-cover" loading="lazy" decoding="async" />
          <span class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/60 to-transparent px-2 py-1 text-xs text-white">{{ p.title }}</span>
        </div>
      </div>
      <p class="mt-2 text-center text-xs text-[var(--el-text-color-secondary)]">← 左右滚动 · 两侧卡片随距离偏转 →</p>
    </div>

    <!-- 说明 -->
    <div class="w-full shrink-0 space-y-1 lg:w-56">
      <p class="pt-1 text-xs leading-5 text-[var(--el-text-color-secondary)]">
        每帧遍历卡片: 卡片中心相对容器中心的偏移比例 δ 决定 rotateY(±45°) 与亮度;
        perspective 挂在滚动容器上, 平移即变成"绕轴旋转的走廊"。这就是 coverflow / 相册墙的核心循环。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
// 3D 透视平移(garden.bradwoods.io/notes/css/3d): 滚动位置 → 卡片旋转姿态
import { galleryPhotos } from './texture'

/** 演示卡片 */
const cards = galleryPhotos.slice(0, 6)

/** 每张卡的旋转角(deg, 响应式驱动样式) */
const angles = ref<number[]>(cards.map(() => 0))

/** 滚动轨道引用 */
const track = ref<HTMLElement | null>(null)

/** rAF 合帧句柄 */
let raf = 0

/** 滚动: 重新计算各卡旋转角 */
function onScroll() {
  cancelAnimationFrame(raf)
  raf = requestAnimationFrame(() => {
    const el = track.value
    if (!el) return
    const cr = el.getBoundingClientRect()
    const cx = cr.left + cr.width / 2
    angles.value = cards.map((_, i) => {
      const card = el.children[i] as HTMLElement | undefined
      if (!card) return 0
      const r = card.getBoundingClientRect()
      const delta = (r.left + r.width / 2 - cx) / cr.width
      return Math.max(-45, Math.min(45, delta * -90))
    })
  })
}

/** 单卡样式: 绕 Y 旋转 + 远处压暗 */
function cardStyle(i: number) {
  const a = angles.value[i] ?? 0
  const dim = Math.abs(a) / 90
  return {
    transform: `rotateY(${a.toFixed(1)}deg)`,
    filter: `brightness(${(1 - dim * 0.35).toFixed(2)})`,
  }
}

onMounted(onScroll)
onBeforeUnmount(() => cancelAnimationFrame(raf))
</script>

<style scoped>
/* 透视空间: 消失点居中; 卡片自身三维化 */
.pan-track {
  perspective: 700px;
}
.pan-card {
  transform-style: preserve-3d;
  transition: transform 0.15s linear, filter 0.15s linear;
  will-change: transform;
}
</style>
