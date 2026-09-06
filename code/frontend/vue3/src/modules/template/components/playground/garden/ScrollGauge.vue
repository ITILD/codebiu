<template>
  <!-- 滚动进度条: 监听内部滚动容器, rAF 节流更新顶部进度条 -->
  <div class="flex flex-col gap-4 lg:flex-row">
    <div class="relative h-64 flex-1 overflow-hidden rounded-md border border-[var(--el-border-color-light)] bg-[var(--el-fill-color-light)]">
      <!-- 顶部进度条: width 跟随滚动比例 -->
      <div class="absolute inset-x-0 top-0 z-10 h-1 bg-[var(--el-border-color-lighter)]">
        <div class="h-full bg-[var(--el-color-primary)] transition-[width] duration-75" :style="{ width: `${progress * 100}%` }" />
      </div>
      <div ref="scroller" class="h-full overflow-y-auto px-4 py-5 text-sm leading-7" @scroll.passive="onScroll">
        <p v-for="(p, i) in paragraphs" :key="i" class="mb-3">{{ p }}</p>
      </div>
      <span class="pointer-events-none absolute bottom-2 right-3 rounded bg-[var(--el-fill-color)] px-2 py-0.5 text-xs text-[var(--el-text-color-secondary)]">
        {{ Math.round(progress * 100) }}%
      </span>
    </div>

    <!-- 说明 -->
    <div class="w-full shrink-0 space-y-1 lg:w-56">
      <p class="pt-1 text-xs leading-5 text-[var(--el-text-color-secondary)]">
        进度 = scrollTop / (scrollHeight − clientHeight); scroll 事件本身触发频率就很高,
        这里再用 requestAnimationFrame 合帧, 把 DOM 写入(改宽度)压到每帧最多一次。
      </p>
      <p class="text-xs leading-5 text-[var(--el-text-color-secondary)]">
        生产环境把监听对象换成 document.scrollingElement、进度条 fixed 到页顶, 就是阅读进度条。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
// 滚动百分比(garden.bradwoods.io/notes/javascript/web-api/scroll-percent)
/** 当前进度 0~1 */
const progress = ref(0)

/** 滚动容器引用 */
const scroller = ref<HTMLElement | null>(null)

/** rAF 合帧句柄 */
let raf = 0

/** 滚动事件: 合帧后计算进度 */
function onScroll() {
  cancelAnimationFrame(raf)
  raf = requestAnimationFrame(() => {
    const el = scroller.value
    if (!el) return
    const max = el.scrollHeight - el.clientHeight
    progress.value = max > 0 ? el.scrollTop / max : 0
  })
}

onBeforeUnmount(() => cancelAnimationFrame(raf))

/** 演示段落 */
const paragraphs = [
  '花园的四季不是日历上的四格，而是渐变的色环。',
  '春分前后，新叶的颜色是一种近乎透明的嫩绿，阳光下像会发光。',
  '夏至时绿意最浓，叶片厚重，蝉声把午后拉得很长。',
  '秋分之后，叶绿素退场，花青素与类胡萝卜素接管调色盘。',
  '冬至的花园看似荒芜，土壤之下根系仍在缓慢生长。',
  '园丁的功课是记录：几日抽芽、几日现蕾、几日初花。',
  '数字花园亦然——笔记不是文章的坟墓，而是种子的苗圃。',
  '写下即播种，修改即修剪，链接即嫁接，回顾即施肥。',
  '进度条提醒你：读到哪里了，也提醒你：还有多少园地未开垦。',
  '滚到底，再滚回去，观察进度条如何往返丈量这篇小径。',
]
</script>
