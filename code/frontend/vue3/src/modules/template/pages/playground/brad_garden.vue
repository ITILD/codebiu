<template>
  <!-- 数字花园主题子页: 每个区块演示 garden.bradwoods.io 中一种巧妙的可视化技巧(数据驱动渲染) -->
  <div :style="{ ...theme.vars, fontFamily: 'var(--el-font-family)' }" :class="theme.rootClass" class="rounded-lg p-4 md:p-6">
    <!-- 顶栏: 与 PaperCard 同源的纸张配方(噪声 + 渐晕 + 内阴影, overlay 混合) -->
    <div class="relative isolate mb-4 overflow-hidden rounded-lg border border-[#cfc9b8]">
      <div class="bg-[#e7dfc8] p-5 md:p-7">
        <h3 class="text-xl font-bold text-[#2f3a2c] md:text-2xl">数字花园 · 可视化技巧温室</h3>
        <p class="mt-2 max-w-3xl text-sm leading-6 text-[#4d5548]">
          移植自 Brad Woods 的数字花园 garden.bradwoods.io：{{ sections.length }} 个区块演示 {{ groups.length }} 类技巧 ——
          CSS 混合模式(纸张 / 双色调 / 半调 / 扫描线 / 聚光去色)、SVG 滤镜与遮罩、排版细节、
          Web API(滚动 / 观察器 / 视图过渡)、CSS 3D 与"果汁感"设计理念。全部零外部依赖, 只用浏览器原生能力。
        </p>
        <!-- 分组导航: 点击滚到该组第一个区块 -->
        <!-- 本页为数字花园(garden.bradwoods.io)移植演示, 整页使用自带纸张配色(#cfc9b8/#e7dfc8/#a9b39d 等),
             白色胶囊(bg-white/40)是纸张上的高光对比色, 有意不映射 note-* token -->
        <div class="mt-3 flex flex-wrap gap-2">
          <button
            v-for="g in groups"
            :key="g.label"
            class="rounded-full border border-[#a9b39d] bg-white/40 px-3 py-1 text-xs text-[#3c4a37] transition-colors hover:bg-[var(--el-color-primary)] hover:text-white"
            @click="scrollTo(g.items[0].id)"
          >
            {{ g.label }} · {{ g.items.length }}
          </button>
        </div>
      </div>
      <!-- overlay 顶盖: 纸张质感 -->
      <div class="pointer-events-none absolute inset-0" :style="heroOverlay" />
    </div>

    <div class="grid gap-4 lg:grid-cols-[190px_minmax(0,1fr)]">
      <!-- 左侧目录: 本身就是 IntersectionObserver 技巧的现场演示 -->
      <aside class="hidden lg:block">
        <div class="sticky top-4 max-h-[calc(100vh-2rem)] overflow-y-auto pb-2">
          <p class="mb-1 px-3 text-xs text-[var(--el-text-color-secondary)]">目录 · 滚动试试</p>
          <ScrollSpyToc :groups="groups" />
        </div>
      </aside>

      <main class="flex min-w-0 flex-col gap-4">
        <!-- 数据驱动渲染全部演示区块 -->
        <el-card v-for="s in sections" :id="s.id" :key="s.id" shadow="never" class="scroll-mt-24">
          <template #header>
            <SectionHead :title="s.title" :tag="s.tag" :href="s.href" />
          </template>
          <component :is="s.comp" v-bind="s.props" />
          <p v-if="s.principle" class="mt-3 border-t border-dashed border-[var(--el-border-color-lighter)] pt-2 text-xs leading-5 text-[var(--el-text-color-secondary)]">
            {{ s.principle }}
          </p>
        </el-card>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
// 数字花园主题子页: 汇集 garden.bradwoods.io 可视化技巧的组件演示
// (每个区块对应原站一篇笔记; 本页自行注入主题变量, 不复用 ThemeShowcase; 区块配置数据驱动)
import { computed } from 'vue'
import type { Component, CSSProperties } from 'vue'
import { playgroundThemes } from '../../components/playground/themes'
import SectionHead from '../../components/playground/garden/SectionHead.vue'
import ScrollSpyToc from '../../components/playground/garden/ScrollSpyToc.vue'
import PaperCard from '../../components/playground/garden/PaperCard.vue'
import DuotoneImage from '../../components/playground/garden/DuotoneImage.vue'
import HalftoneImage from '../../components/playground/garden/HalftoneImage.vue'
import ScanlineImage from '../../components/playground/garden/ScanlineImage.vue'
import FocusImage from '../../components/playground/garden/FocusImage.vue'
import GooeyBlobs from '../../components/playground/garden/GooeyBlobs.vue'
import DistressFrame from '../../components/playground/garden/DistressFrame.vue'
import WobbleSketch from '../../components/playground/garden/WobbleSketch.vue'
import Ripple from '../../components/playground/garden/Ripple.vue'
import DisplaceZoom from '../../components/playground/garden/DisplaceZoom.vue'
import Hologram from '../../components/playground/garden/Hologram.vue'
import MaskLens from '../../components/playground/garden/MaskLens.vue'
import FadeMask from '../../components/playground/garden/FadeMask.vue'
import PatternForge from '../../components/playground/garden/PatternForge.vue'
import OrganicGradient from '../../components/playground/garden/OrganicGradient.vue'
import Emboss from '../../components/playground/garden/Emboss.vue'
import ShapeFlow from '../../components/playground/garden/ShapeFlow.vue'
import DropCap from '../../components/playground/garden/DropCap.vue'
import ProseStack from '../../components/playground/garden/ProseStack.vue'
import ScrollGauge from '../../components/playground/garden/ScrollGauge.vue'
import SectionMeter from '../../components/playground/garden/SectionMeter.vue'
import ThemeHeader from '../../components/playground/garden/ThemeHeader.vue'
import InfiniteFeed from '../../components/playground/garden/InfiniteFeed.vue'
import TiltCard3D from '../../components/playground/garden/TiltCard3D.vue'
import PerspectivePan from '../../components/playground/garden/PerspectivePan.vue'
import RotateYShelf from '../../components/playground/garden/RotateYShelf.vue'
import SlidePager from '../../components/playground/garden/SlidePager.vue'
import ScrollDrawTimeline from '../../components/playground/garden/ScrollDrawTimeline.vue'
import ViewTransitionGallery from '../../components/playground/garden/ViewTransitionGallery.vue'
import JuicyButton from '../../components/playground/garden/JuicyButton.vue'
import SkinSwitcher from '../../components/playground/garden/SkinSwitcher.vue'
import GrowUI from '../../components/playground/garden/GrowUI.vue'
import { NOISE_URL } from '../../components/playground/garden/texture'
import type { TimelineItem, TocGroup } from '../../components/playground/garden/types'

/** 当前主题 */
const theme = playgroundThemes.find((t) => t.key === 'brad_garden')!

/** 演示区块定义 */
interface SectionDef {
  /** 区块 id(锚点) */
  id: string
  /** 标题 */
  title: string
  /** 技术标签 */
  tag: string
  /** 原站笔记链接 */
  href: string
  /** 演示组件 */
  comp: Component
  /** 传给组件的 props(可选) */
  props?: Record<string, unknown>
  /** 区块底部的原理说明 */
  principle?: string
}

const G = 'https://garden.bradwoods.io'

/** 描线时间轴内容 */
const timeline: TimelineItem[] = [
  { phase: '播种 SOW', text: '想法落进土壤：需求与素材先归档成一颗种子。' },
  { phase: '发芽 SPROUT', text: '结构长出骨架：布局与栅格先立起来。' },
  { phase: '展叶 LEAF', text: '组件填充枝干：配色与排版逐层展开。' },
  { phase: '开花 BLOOM', text: '微交互点缀：动效与反馈让页面有生气。' },
  { phase: '结果 FRUIT', text: '性能与可用性沉淀：页面可以被分享与复用。' },
]

/** 全部演示区块(按目录顺序) */
const sections: SectionDef[] = [
  // ── 纸张与混合 ─────────────────────────────────────────────
  {
    id: 'paper', title: '纸张质感 Paper', tag: 'mix-blend-mode · overlay', href: `${G}/notes/css/blend-modes`, comp: PaperCard,
    principle: '原理: 纸色底层之上，把噪声图、角落渐晕与 inset 阴影做成顶盖并以 overlay 混合 —— 暗处更暗、亮处更亮，纹理同时"印"进夹在中间的内容；外层 isolation: isolate 防止混合泄漏到页面背景。',
  },
  {
    id: 'duotone', title: '双色调 Duotone', tag: 'mix-blend-mode · multiply + screen', href: `${G}/notes/css/blend-modes`, comp: DuotoneImage,
    principle: '原理: 图片先 grayscale(1)，screen 层把亮部染成亮色、multiply 层把暗部染成暗色，两个颜色即可重现双色印刷海报。',
  },
  {
    id: 'halftone', title: '半调网点 Halftone', tag: 'mix-blend-mode · hard-light', href: `${G}/notes/css/blend-modes`, comp: HalftoneImage,
    principle: '原理: radial-gradient 平铺出旋转点阵，图像以 grayscale + hard-light 压上去，父级 filter: contrast(1800%) 把柔和边界压成锐利网点，模拟老报纸印刷。',
  },
  {
    id: 'scanline', title: '扫描线 Scanlines', tag: 'mix-blend-mode · overlay', href: `${G}/notes/css/blend-modes`, comp: ScanlineImage,
    principle: '原理: repeating-linear-gradient 生成等宽条纹，overlay 混合让黑线压暗暗部、白线提亮亮部 —— 一层代码得到 CRT 质感。',
  },
  {
    id: 'focus', title: '彩色聚光 Colored Area', tag: 'mix-blend-mode · saturation', href: `${G}/notes/css/blend-modes`, comp: FocusImage,
    principle: '原理: saturation 混合取顶层的"饱和度"与底层的"色相/明度"。黑色饱和度为 0，黑色遮罩扫过之处即被去色；径向渐变挖出的透明圆孔则保留色彩，跟随鼠标移动。',
  },
  // ── SVG 滤镜 ──────────────────────────────────────────────
  {
    id: 'gooey', title: '果冻融合 Gooey', tag: 'SVG · blur + colormatrix', href: `${G}/notes/svg/filters`, comp: GooeyBlobs,
    principle: '原理: feGaussianBlur 先把图形糊开，feColorMatrix 把 alpha 通道陡化，靠近的模糊边缘一起越过阈值，看起来就像融为一体的果冻 —— 粘稠的"元球"效果只需要两个 primitive。',
  },
  {
    id: 'distress', title: '蚀刻斑驳 Distress', tag: 'SVG · turbulence + composite', href: `${G}/notes/svg/filters`, comp: DistressFrame,
    principle: '原理: feTurbulence 生成噪声，feComponentTransfer 把噪声阈值化成镂空遮罩，feComposite operator="in" 只保留遮罩覆盖的部分 —— 海报边缘的腐蚀感由此而来。',
  },
  {
    id: 'wobble', title: '手绘抖动 Wobble', tag: 'SVG · displacement', href: `${G}/notes/svg/filters/fedisplacementmap`, comp: WobbleSketch,
    principle: '原理: feTurbulence 生成噪声场，feDisplacementMap 按噪声的 R/G 通道推挤源图形的 x/y 坐标 —— 直线变颤线，印刷体变手写体。',
  },
  {
    id: 'ripple', title: '涟漪水面 Ripple', tag: 'SVG · SMIL 动画', href: `${G}/notes/svg/filters/fedisplacementmap`, comp: Ripple,
    principle: '原理: 与抖动同源的位移滤镜，但基频由 SVG 原生 <animate> 往复驱动 —— 横低纵高的频率把波纹拉长成水面，零 JS 得到荡漾动画。',
  },
  {
    id: 'liquid', title: '液态缩放 Displace Zoom', tag: 'SVG + CSS transform', href: `${G}/notes/svg/filters/fedisplacementmap`, comp: DisplaceZoom,
    principle: '原理: CSS scale 负责平滑放大，feDisplacementMap 负责把像素按噪声场推挤；悬停时用 rAF 把位移强度从 0 补间到目标值，液化便"呼吸"般浮现。',
  },
  {
    id: 'hologram', title: '全息投影 Hologram', tag: '纯 CSS · 滤镜叠层', href: `${G}/notes/svg/hologram`, comp: Hologram,
    principle: '原理: sepia + hue-rotate 把图压成单色荧光，两枚反向 drop-shadow 制造红青色散，repeating-linear-gradient 是扫描线，一条高光带循环掠过即是"信号扫过"。',
  },
  // ── 质感与图案 ────────────────────────────────────────────
  {
    id: 'lens', title: '放大镜遮罩 Mask Lens', tag: 'CSS mask · 径向渐变', href: `${G}/notes/svg/mask`, comp: MaskLens,
    principle: '原理: mask-image: radial-gradient 在顶层图上挖出"只有圆内不透明"的遮罩，圆心跟随鼠标；底层是同图的灰度版 —— 圆孔内彩色、圆外黑白，不需要第二份裁剪资源。',
  },
  {
    id: 'fade', title: '渐隐融入 Fade Mask', tag: 'CSS mask · 线性渐变', href: `${G}/notes/svg/mask`, comp: FadeMask,
    principle: '原理: mask 渐变从黑色(显示)过渡到透明(隐藏)，图片边缘便与下方背景无缝融合 —— 横幅配图常用它避免"生硬的矩形边"。',
  },
  {
    id: 'pattern', title: '图案工厂 Pattern', tag: 'SVG pattern · 渐变平铺', href: `${G}/notes/svg/pattern`, comp: PatternForge,
    principle: '原理: 渐变函数本身可平铺，颜色断点处"硬切"即得几何图案 —— repeating-linear-gradient 织条纹、radial-gradient 画圆点、conic-gradient 拼棋盘。',
  },
  {
    id: 'organic', title: '有机渐变 Organic', tag: 'blur 色块 · 关键帧', href: `${G}/notes/shaders/gradient`, comp: OrganicGradient,
    principle: '原理: 每枚色块只是纯色圆，filter: blur 把边界融开；各圆按不同周期游走，叠加后即"活的网格渐变" —— 设计工具里的 mesh gradient 本质就是这层窗户纸。',
  },
  {
    id: 'emboss', title: '浮雕 Emboss', tag: 'text/box-shadow · 极坐标', href: `${G}`, comp: Emboss,
    principle: '原理: 物体与背景同色，只靠两枚偏移影子塑形：朝光侧白影、背光侧黑影；角度换算成 cos/sin 偏移即可让"太阳"绕字一周，正负号一翻就是凹陷。',
  },
  // ── 排版文字 ──────────────────────────────────────────────
  {
    id: 'shape', title: '文字环绕 Shape Flow', tag: 'shape-outside · float', href: `${G}/notes/css/floating-image`, comp: ShapeFlow,
    principle: '原理: shape-outside 只对浮动元素生效，传 circle() 或与 clip-path 相同的 polygon()，文字便沿轮廓绕行 —— 它改变"文字可占区域"，不裁剪图像，所以两者要成对使用。',
  },
  {
    id: 'dropcap', title: '首字下沉 Drop Cap', tag: 'float · ::first-letter 思路', href: `${G}/notes/css/floating-image`, comp: DropCap,
    principle: '原理: 首字 float 左浮后，后续文字环绕下沉字符排列；font-size 放大 n 倍时 line-height 需同步压缩，否则首字会占据 n 行高的空白。initial-letter 更语义化但兼容性未到。',
  },
  {
    id: 'prose', title: '段落节奏 Prose', tag: 'measure · leading · tracking', href: `${G}/notes/css/layout-component`, comp: ProseStack,
    principle: '原理: 45–75ch 版心与 1.5–1.8 行高是可读性研究的经典结论；"ch"等于数字 0 的宽度，与字体无关地近似一个中文字符。排印没有唯一正确值，只有此刻最舒服的参数。',
  },
  // ── Web API ───────────────────────────────────────────────
  {
    id: 'gauge', title: '滚动进度 Scroll Gauge', tag: 'scroll + rAF 合帧', href: `${G}/notes/javascript/web-api/scroll-percent`, comp: ScrollGauge,
    principle: '原理: 进度 = scrollTop / (scrollHeight − clientHeight)；scroll 事件触发频率很高，用 requestAnimationFrame 合帧把 DOM 写入压到每帧最多一次。换成 document 尺度就是阅读进度条。',
  },
  {
    id: 'meter', title: '区块计量 Section Meter', tag: 'IntersectionObserver', href: `${G}/notes/javascript/web-api/intersection-observer`, comp: SectionMeter,
    principle: '原理: threshold 0.6 表示区块 60% 进入视口才算"到访"；visited 集合只增不减 —— 计量的是"探索进度"而非"当前位置"，适合新手引导与课程完成度。',
  },
  {
    id: 'header', title: '动态主题导航 Theme Header', tag: 'IO + 滚动方向', href: `${G}/notes/javascript/web-api/intersection-observer/dynamic-header`, comp: ThemeHeader,
    principle: '原理: 记住上一次 scrollTop，新值更大即在下滚 → 头部 translateY(-100%) 藏起，小了即浮回；区块配色由 IntersectionObserver 的交叉信息切换。',
  },
  {
    id: 'feed', title: '无限信息流 Infinite Feed', tag: '哨兵元素 · 骨架屏', href: `${G}/notes/javascript/web-api/intersection-observer/infinite-scroll`, comp: InfiniteFeed,
    principle: '原理: 列表末尾挂一个 1px 哨兵 div，其进入视口即触发加载 —— 不需要监听 scroll 也不需要计算高度；骨架屏掩盖网络延迟。',
  },
  // ── 3D 与过渡 ─────────────────────────────────────────────
  {
    id: 'tilt3d', title: 'CSS 3D 透视', tag: 'perspective · preserve-3d', href: `${G}/notes/css/3d`, comp: TiltCard3D,
    principle: '原理: 父级 perspective 开启三维空间，子级 rotateX/rotateY 随鼠标倾斜；内容分层 translateZ 产生视差纵深，preserve-3d 让孙级立方体也留在三维空间里。',
  },
  {
    id: 'pan', title: '透视平移 Coverflow', tag: 'perspective · 滚动驱动', href: `${G}/notes/css/3d`, comp: PerspectivePan,
    principle: '原理: 每帧遍历卡片，中心偏移比例 δ 决定 rotateY(±45°) 与亮度；perspective 挂在滚动容器上，平移即变成"绕轴旋转的走廊" —— coverflow 的核心循环。',
  },
  {
    id: 'shelf', title: '旋转书架 Bookshelf', tag: 'preserve-3d · 平面折叠', href: `${G}/notes/css/3d`, comp: RotateYShelf,
    principle: '原理: 书 = preserve-3d 容器，封面是 rotateY(90°) 后"折"进深度的平面；悬停整本书 rotateY(-32°) 转出，侧对的封面随之可见 —— 一本书由两张面拼成，全靠变换而非图片。',
  },
  {
    id: 'pager', title: '滑动分页 Scroll Snap', tag: 'scroll-snap · 两行 CSS', href: `${G}/notes/css/3d`, comp: SlidePager,
    principle: '原理: scroll-snap-type: x mandatory + 子项 scroll-snap-align: center，两行声明完成"翻页吸附"；JS 只负责把滚动位置换算成页码同步圆点。',
  },
  {
    id: 'draw', title: '滚动描线 Draw on Scroll', tag: 'SVG · clip-path', href: `${G}/notes/svg/scroll-driven-draw-animation`, comp: ScrollDrawTimeline,
    props: { items: timeline },
    principle: '原理: 曲线完整渲染但被 clipPath 矩形裁剪，滚动时按进度平移/增高裁剪框，只露出"已画过"的部分；vector-effect: non-scaling-stroke 保证拉伸后线宽一致。',
  },
  {
    id: 'transition', title: '视图过渡 View Transition', tag: 'document.startViewTransition', href: `${G}/notes/javascript/web-api/view-transition`, comp: ViewTransitionGallery,
  },
  // ── 设计理念 ──────────────────────────────────────────────
  {
    id: 'juice', title: '果汁感交互 Juice', tag: 'squash & stretch · 粒子反馈', href: `${G}/notes/design/juice`, comp: JuicyButton,
  },
  {
    id: 'skin', title: '换肤工坊 Personalization', tag: 'CSS 变量 · localStorage', href: `${G}/notes/design/personalization`, comp: SkinSwitcher,
    principle: '原理: 把用户偏好写进局部 CSS 变量(--el-color-primary / --el-border-radius-base…)，Element Plus 组件无需重渲染即完成换肤；偏好存 localStorage，下次回来仍是"你的"界面。',
  },
  {
    id: 'grow', title: '生长式 UI User-Driven', tag: '渐进式披露 · 里程碑', href: `${G}/notes/design/user-driven-ui`, comp: GrowUI,
    principle: '原理: 渐进式披露 —— 新手看到的界面越小越好，功能在"用得到时"才出现；解锁前用占位告诉用户"再往前一步有什么"，兼具引导与激励。',
  },
]

/** 目录分组(按 sections 顺序聚合) */
const groups = computed<TocGroup[]>(() => {
  const defs: { label: string; from: string; to: string }[] = [
    { label: '纸张与混合', from: 'paper', to: 'focus' },
    { label: 'SVG 滤镜', from: 'gooey', to: 'hologram' },
    { label: '质感与图案', from: 'lens', to: 'emboss' },
    { label: '排版文字', from: 'shape', to: 'prose' },
    { label: 'Web API', from: 'gauge', to: 'feed' },
    { label: '3D 与过渡', from: 'tilt3d', to: 'transition' },
    { label: '设计理念', from: 'juice', to: 'grow' },
  ]
  return defs.map(({ label, from, to }) => ({
    label,
    items: sections.slice(sections.findIndex((s) => s.id === from), sections.findIndex((s) => s.id === to) + 1)
      .map((s) => ({ id: s.id, label: s.title.split(' ')[0] })),
  }))
})

/** 顶栏纸张配方: 噪声 + 渐晕 + inset 阴影, overlay 混合 */
const heroOverlay: CSSProperties = {
  boxShadow: 'inset 0 0 46px 8px hsla(0, 0%, 0%, 0.22)',
  background: `${NOISE_URL}, linear-gradient(to bottom right, hsla(0, 0%, 0%, 0) 45%, hsla(0, 0%, 0%, 0.9) 130%)`,
  mixBlendMode: 'overlay',
}

/** 平滑滚动到区块 */
function scrollTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
</script>
