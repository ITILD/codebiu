<template>
  <!-- 手绘抖动: feTurbulence 噪声经 feDisplacementMap 扭曲源图形, 模拟不稳定的手绘线条 -->
  <div class="flex flex-col gap-4 lg:flex-row">
    <div class="relative flex flex-1 items-center justify-center overflow-hidden rounded-md border border-[var(--el-border-color-light)] bg-[var(--el-bg-color-page)] py-10">
      <svg width="0" height="0" class="absolute" aria-hidden="true">
        <defs>
          <filter id="gdn-wobble">
            <feTurbulence ref="noise" type="fractalNoise" :baseFrequency="state.freq" numOctaves="1" result="noise" seed="2" />
            <feDisplacementMap in="SourceGraphic" in2="noise" :scale="state.scale" xChannelSelector="R" yChannelSelector="G" />
          </filter>
        </defs>
      </svg>
      <div class="px-8 text-center" :style="{ filter: 'url(#gdn-wobble)' }">
        <svg width="120" height="90" viewBox="0 0 120 90" fill="none" class="mx-auto" aria-hidden="true">
          <path d="M60 85 V45" stroke="var(--el-color-primary)" stroke-width="4" stroke-linecap="round" />
          <path d="M60 50 C60 30 44 22 26 24 C28 42 44 50 60 50 Z" fill="var(--el-color-primary-light-5)" stroke="var(--el-color-primary-dark-2)" stroke-width="3" />
          <path d="M60 50 C60 38 70 30 88 32 C86 44 76 50 60 50 Z" fill="var(--el-color-primary-light-5)" stroke="var(--el-color-primary-dark-2)" stroke-width="3" />
        </svg>
        <p class="mt-3 font-serif text-2xl font-bold text-[var(--el-text-color-primary)]">手绘笔记</p>
      </div>
      <span class="pointer-events-none absolute bottom-2 left-3 text-xs text-[var(--el-text-color-secondary)]">点"抖一抖"看线条活过来</span>
    </div>

    <!-- 控制面板 -->
    <div class="w-full shrink-0 space-y-3 lg:w-56">
      <div class="flex items-center gap-2">
        <span class="w-14 shrink-0 text-xs text-[var(--el-text-color-secondary)]">扭度</span>
        <el-slider v-model="state.scale" :min="0" :max="40" size="small" class="flex-1" />
      </div>
      <div class="flex items-center gap-2">
        <span class="w-14 shrink-0 text-xs text-[var(--el-text-color-secondary)]">颗粒</span>
        <el-slider v-model="state.freq" :min="0.005" :max="0.06" :step="0.005" size="small" class="flex-1" />
      </div>
      <div class="flex gap-2">
        <el-button size="small" type="primary" plain @click="shake">抖一抖</el-button>
        <el-button size="small" :type="boiling ? 'primary' : 'info'" plain @click="toggleBoil">{{ boiling ? '停止沸腾' : '持续沸腾' }}</el-button>
      </div>
      <p class="text-xs leading-5 text-[var(--el-text-color-secondary)]">
        feDisplacementMap 用 in2(噪声图)的 R/G 通道逐像素搬移 in(源图形), scale 控制搬移强度;
        逐帧改噪声 seed, 线条就像 boiling line 动画一样"沸腾"。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
// feDisplacementMap(garden.bradwoods.io/notes/svg/filters/fedisplacementmap):
// in=源图形, in2=噪声 map, scale/xChannelSelector/yChannelSelector 控制扭曲

/** 可调参数 */
const state = reactive({ scale: 14, freq: 0.015 })

/** 噪声 primitive 引用(逐帧改 seed) */
const noise = ref<SVGFETurbulenceElement | null>(null)

/** 是否持续沸腾 */
const boiling = ref(false)

/** 帧循环句柄 */
let raf = 0

/** 单次抖动: scale 从 0 弹到目标再回弹(rAF 补间) */
function shake() {
  const start = performance.now()
  const target = state.scale
  const tick = (t: number) => {
    const p = Math.min(1, (t - start) / 260)
    const ease = Math.sin(p * Math.PI) * (1 - p * 0.4)
    noise.value?.parentElement?.querySelector('feDisplacementMap')?.setAttribute('scale', String(Math.round(target * ease + 2)))
    if (p < 1) requestAnimationFrame(tick)
  }
  requestAnimationFrame(tick)
}

/** 开关持续沸腾 */
function toggleBoil() {
  boiling.value = !boiling.value
  cancelAnimationFrame(raf)
  if (!boiling.value) return
  let seed = 2
  let last = 0
  const loop = (t: number) => {
    // 每 90ms 换一次 seed, 得到手绘"沸腾"效果
    if (t - last > 90) {
      seed = (seed + 1) % 100
      noise.value?.setAttribute('seed', String(seed))
      last = t
    }
    raf = requestAnimationFrame(loop)
  }
  raf = requestAnimationFrame(loop)
}

onBeforeUnmount(() => cancelAnimationFrame(raf))
</script>
