<template>
  <!-- 动态主题导航: 下滚隐藏/上滚浮现的 sticky 头, 且颜色随所处区块切换 -->
  <div class="flex flex-col gap-4 lg:flex-row">
    <div ref="scroller" class="relative h-64 flex-1 overflow-y-auto rounded-md border border-[var(--el-border-color-light)]" @scroll.passive="onScroll">
      <!-- sticky 头: translate 跟随滚动方向隐藏/浮现, 配色随区块切换 -->
      <header
        class="sticky top-0 z-10 flex h-11 items-center gap-2 px-4 text-sm font-semibold text-white transition-all duration-300"
        :class="[currentCls, hidden ? '-translate-y-full' : 'translate-y-0']"
      >
        <span>温室日志</span>
        <span class="ml-auto text-xs font-normal opacity-80">{{ current }}</span>
      </header>
      <section v-for="s in sections" :key="s.name" :data-season="s.name" class="p-6" :style="{ background: s.bg }">
        <h4 class="mb-2 text-base font-bold" :style="{ color: s.fg }">{{ s.name }}</h4>
        <p class="text-sm leading-6" :style="{ color: s.fg }">{{ s.text }}</p>
      </section>
    </div>

    <!-- 说明 -->
    <div class="w-full shrink-0 space-y-1 lg:w-56">
      <p class="pt-1 text-xs leading-5 text-[var(--el-text-color-secondary)]">
        方向检测只需记住上一次 scrollTop: 新值更大即在下滚 → 头部 translateY(-100%) 藏起;
        小了即在上滚 → 立刻浮回。区块配色由 IntersectionObserver 交叉信息切换。
      </p>
      <p class="text-xs leading-5 text-[var(--el-text-color-secondary)]">
        阅读类页面搭配使用, 阅读时导航让路、回看时导航归来, 屏幕永远不浪费。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
// 滚动方向感知导航(garden.bradwoods.io/notes/javascript/web-api/intersection-observer):
// scrollTop 差值判断方向 + IO 切换主题
/** 区块定义 */
interface Section {
  name: string
  text: string
  bg: string
  fg: string
  cls: string
}

/** 四季区块与对应头部配色 */
const sections: Section[] = [
  { name: '春 · 萌发', text: '新叶初绽, 土壤解冻, 一年中的播种季从这里开始。', bg: '#eef4e4', fg: '#3f5a35', cls: 'bg-[#5a8a4a]' },
  { name: '夏 · 盛放', text: '枝叶最密的时节, 蝉声与灌溉构成了午后的背景音。', bg: '#e4f0ee', fg: '#2f5a52', cls: 'bg-[#3f7a6e]' },
  { name: '秋 · 结果', text: '果实压弯枝头, 采摘要趁晴天, 伤口要留霜后处理。', bg: '#f4ecdd', fg: '#6b4f26', cls: 'bg-[#a8762e]' },
  { name: '冬 · 蓄力', text: '落叶归土, 养分回流根系, 静候下一个循环。', bg: '#e9e9ee', fg: '#3d4152', cls: 'bg-[#565b73]' },
]

/** 当前所处季节(头部右侧显示) */
const current = ref(sections[0].name)

/** 头部配色: 跟随当前季节 */
const currentCls = computed(() => sections.find((s) => s.name === current.value)?.cls ?? sections[0].cls)

/** 头部是否隐藏(下滚时) */
const hidden = ref(false)

/** 上一次 scrollTop(判断方向用) */
let lastTop = 0

/** rAF 合帧句柄 */
let raf = 0

/** 滚动容器引用 */
const scroller = ref<HTMLElement | null>(null)

/** 观察器实例 */
let io: IntersectionObserver | null = null

/** 滚动方向检测: 合帧后比较 scrollTop 差值 */
function onScroll() {
  cancelAnimationFrame(raf)
  raf = requestAnimationFrame(() => {
    const el = scroller.value
    if (!el) return
    hidden.value = el.scrollTop > lastTop + 2 && el.scrollTop > 40
    lastTop = el.scrollTop
  })
}

onMounted(() => {
  io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (e.isIntersecting) current.value = (e.target as HTMLElement).dataset.season ?? ''
      }
    },
    // 头部占到视口上部, 用负 rootMargin 压出"判定线"于容器上部
    { root: scroller.value, rootMargin: '-45% 0px -50% 0px', threshold: 0 },
  )
  scroller.value?.querySelectorAll<HTMLElement>('[data-season]').forEach((el) => io?.observe(el))
})

onBeforeUnmount(() => {
  io?.disconnect()
  cancelAnimationFrame(raf)
})
</script>
