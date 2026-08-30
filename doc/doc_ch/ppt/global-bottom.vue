<!-- 全局底层 (global-bottom.vue)   https://cn.sli.dev/features/global-layers -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useNav } from '@slidev/client'
import seedrandom from 'seedrandom'

/**
 * 幻灯片背景光效组件
 * 基于模糊多边形实现的动态光晕效果
 *
 * 支持的前置元数据 (Frontmatter):
 * - glow: 分布模式 ('left' | 'right' | 'top' | 'bottom' | 'full' | 'center' 等)
 * - glowOpacity: 透明度 (默认 0.4)
 * - glowHue: 色相偏移角度 (默认 0)
 * - glowSeed: 随机种子，设为 false 则每页随机
 */

// --- 类型定义 ---

type Range = [number, number]

type Distribution =
  | 'full'
  | 'top'
  | 'bottom'
  | 'left'
  | 'right'
  | 'top-left'
  | 'top-right'
  | 'bottom-left'
  | 'bottom-right'
  | 'center'
  | 'topmost'

interface SlideFrontmatter {
  glow?: Distribution
  glowOpacity?: number
  glowHue?: number
  glowSeed?: string | boolean
}

// --- 常量配置 ---

const CONFIG = {
  overflow: 0.3,      // 点位溢出边界比例
  disturb: 0.3,       // 扰动幅度
  disturbChance: 0.3, // 发生扰动的概率
  pointCounts: [10, 6, 3] // 三层多边形的顶点数量
}

// --- 辅助函数 ---

/**
 * 计算两点之间的欧几里得距离平方
 * 用于比较距离，避免开方运算以提高性能
 */
const distance2 = ([x1, y1]: Range, [x2, y2]: Range): number =>
  (x2 - x1) ** 2 + (y2 - y1) ** 2

/**
 * 根据分布策略计算坐标限制范围
 */
const getDistributionLimits = (dist: Distribution): { x: Range; y: Range } => {
  const min = -0.2
  const max = 1.2
  let x: Range = [min, max]
  let y: Range = [min, max]

  const intersect = (a: Range, b: Range): Range => [
    Math.max(a[0], b[0]),
    Math.min(a[1], b[1])
  ]

  // 支持组合策略，如 'top-left' 会被 split 为 ['top', 'left']
  dist.split('-').forEach((part) => {
    switch (part) {
      case 'topmost': y = intersect(y, [-0.5, 0]); break
      case 'top': y = intersect(y, [min, 0.6]); break
      case 'bottom': y = intersect(y, [0.4, max]); break
      case 'left': x = intersect(x, [min, 0.6]); break
      case 'right': x = intersect(x, [0.4, max]); break
      case 'xcenter': x = intersect(x, [0.25, 0.75]); break
      case 'ycenter': y = intersect(y, [0.25, 0.75]); break
      case 'center':
        x = intersect(x, [0.25, 0.75])
        y = intersect(y, [0.25, 0.75])
        break
      case 'full':
        x = intersect(x, [0, 1])
        y = intersect(y, [0, 1])
        break
    }
  })

  return { x, y }
}

// --- 核心逻辑 ---

const { currentSlideRoute } = useNav()

// 获取当前幻灯片的 frontmatter，确保类型安全
const frontmatter = computed<SlideFrontmatter>(
  () => (currentSlideRoute.value.meta?.slide as any)?.frontmatter || {}
)

// 提取配置项
const distribution = computed(() => frontmatter.value.glow || 'full')
const opacity = computed(() => +(frontmatter.value.glowOpacity ?? 0.4))
const hue = computed(() => +(frontmatter.value.glowHue || 0))
const seed = computed(() => {
  const s = frontmatter.value.glowSeed
  return (s === false || s === 'false') ? Date.now().toString() : (s || 'default')
})

/**
 * 生成多边形路径字符串
 * @param count 顶点数量
 */
const usePolygonPath = (count: number) => {
  // 存储当前的顶点坐标
  const points = ref<Range[]>([])

  // 生成新的随机点集
  const generatePoints = (): Range[] => {
    const limits = getDistributionLimits(distribution.value)
    // 结合种子和幻灯片编号，确保同一页刷新后形状一致，不同页形状不同
    const rng = seedrandom(`${seed.value}-${currentSlideRoute.value.no}`)

    const randomBetween = ([a, b]: Range) => rng() * (b - a) + a

    const applyDisturbance = (val: number) => {
      // 基础溢出处理
      let res = val * (1 + CONFIG.overflow * 2) - CONFIG.overflow
      // 随机扰动
      if (rng() < CONFIG.disturbChance) {
        res += (rng() - 0.5) * CONFIG.disturb
      }
      return res
    }

    return Array.from({ length: count }, () => [
      applyDisturbance(randomBetween(limits.x)),
      applyDisturbance(randomBetween(limits.y))
    ])
  }

  // 初始化点
  points.value = generatePoints()

  // 计算 CSS clip-path 所需的字符串格式 "x% y%, x% y%..."
  const pathString = computed(() =>
    points.value.map(([x, y]) => `${x * 100}% ${y * 100}%`).join(', ')
  )

  // 页面切换时，平滑过渡点到新位置
  const transitionPoints = () => {
    // 直接替换点位,依赖 CSS transition: all 2.5s ease 实现平滑效果
    points.value = generatePoints()
  }

  watch(currentSlideRoute, transitionPoints)

  return pathString
}

// 生成三层不同密度的多边形路径
const poly1 = usePolygonPath(CONFIG.pointCounts[0])
const poly2 = usePolygonPath(CONFIG.pointCounts[1])
const poly3 = usePolygonPath(CONFIG.pointCounts[2])

</script>

<template>
  <div class="relative w-full h-full">
    <!-- 背景光效容器(苔绿自然色调) -->
    <div class="absolute inset-0 z-[-10] overflow-hidden pointer-events-none transform-gpu"
      :style="{ filter: `blur(70px) hue-rotate(${hue}deg)` }" aria-hidden="true">
      <!-- 第一层：主光晕(苔绿) -->
      <div class="absolute inset-0 aspect-video bg-gradient-to-r from-[#3d7a4d] to-[#1e5b3a]" :style="{
        clipPath: `polygon(${poly1})`,
        opacity: opacity
      }" />

      <!-- 第二层：次级光晕(深绿) -->
      <div class="absolute inset-0 aspect-video bg-gradient-to-l from-[#3d7a4d] to-[#2a6b45]" :style="{
        clipPath: `polygon(${poly2})`,
        opacity: opacity
      }" />

      <!-- 第三层：高光点缀(嫩绿) -->
      <div class="absolute inset-0 aspect-video bg-gradient-to-t from-[#7fce8f] to-[#d8f2dc]" :style="{
        clipPath: `polygon(${poly3})`,
        opacity: 0.2
      }" />
    </div>

    <!-- 页脚标识 -->
    <footer class="absolute bottom-0 right-0 p-2 text-sm opacity-50">
      codebiu
    </footer>
  </div>
</template>

<style scoped>
/*
  应用过渡效果到所有变化属性
  注意：clip-path 的过渡在现代浏览器中已得到良好支持
*/
div[class*="bg-gradient"] {
  transition:
    clip-path 2.5s cubic-bezier(0.4, 0, 0.2, 1),
    opacity 2.5s ease;
}

/* 明色模式下大幅减弱光晕，避免暗色调元素污染明色背景 */
:deep(.light) div[class*="bg-gradient"] {
  opacity: 0.15 !important;
  filter: saturate(0.6) brightness(1.1);
}
</style>
