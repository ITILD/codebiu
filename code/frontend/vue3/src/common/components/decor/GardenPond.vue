<template>
  <!-- 小池: 水岸渐变 + SMIL feTurbulence 位移滤镜驱动涟漪(零 JS 动画),
       荷叶/荷花/落石/薄雾点缀; 配色全部取 --note-* 变量, 亮暗自适应 -->
  <svg
    class="pond block h-auto w-full select-none"
    viewBox="0 0 900 200"
    preserveAspectRatio="xMidYMax meet"
    role="img"
    aria-label="一方涟漪轻荡的小池"
  >
    <defs>
      <linearGradient id="pond-water" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" class="pond-stop-top" />
        <stop offset="100%" class="pond-stop-bottom" />
      </linearGradient>
      <clipPath id="pond-clip">
        <path :d="WATER_D" />
      </clipPath>
      <!-- 涟漪滤镜: turbulence 噪声场经 SMIL 往复变化, displacementMap 推挤水纹像素 -->
      <filter id="pond-ripple" x="-5%" y="-5%" width="110%" height="110%">
        <feTurbulence type="turbulence" baseFrequency="0.009 0.05" numOctaves="2" seed="7" result="noise">
          <animate
            v-if="!reducedMotion"
            attributeName="baseFrequency"
            values="0.009 0.05; 0.013 0.032; 0.009 0.05"
            keyTimes="0; 0.5; 1"
            dur="7.5s"
            repeatCount="indefinite"
          />
        </feTurbulence>
        <feDisplacementMap in="SourceGraphic" in2="noise" scale="8" xChannelSelector="R" yChannelSelector="G" />
      </filter>
    </defs>

    <!-- 水体 -->
    <path :d="WATER_D" class="water-fill" />

    <!-- 水纹/光圈/扩散涟漪: 统一裁剪到水形, 并被涟漪滤镜荡漾 -->
    <g clip-path="url(#pond-clip)" filter="url(#pond-ripple)">
      <ellipse v-for="(g, i) in glints" :key="`g${i}`" :cx="g.cx" :cy="g.cy" :rx="g.rx" ry="3.4" class="water-shine" />
      <path v-for="(l, i) in lines" :key="`l${i}`" :d="l.d" class="water-line" :style="{ opacity: l.opacity }" stroke-width="1.2" />
      <circle
        v-for="(r, i) in rings"
        :key="`r${i}`"
        :cx="r.cx"
        :cy="r.cy"
        :r="reducedMotion ? r.r * 0.5 : 3"
        class="water-line"
        :style="{ opacity: reducedMotion ? 0.22 : undefined }"
        stroke-width="1.2"
      >
        <template v-if="!reducedMotion">
          <animate attributeName="r" :values="`3; ${r.r}`" :dur="`${r.dur}s`" :begin="r.begin" repeatCount="indefinite" />
          <animate
            attributeName="opacity"
            values="0; 0.5; 0"
            keyTimes="0; 0.25; 1"
            :dur="`${r.dur}s`"
            :begin="r.begin"
            repeatCount="indefinite"
          />
        </template>
      </circle>
    </g>

    <!-- 薄雾: 沿水岸横移 -->
    <g class="pond-mist">
      <ellipse v-for="(m, i) in mists" :key="`m${i}`" :cx="m.cx" :cy="m.cy" :rx="m.rx" ry="13" class="mist" />
    </g>

    <!-- 岸石 -->
    <ellipse v-for="(s, i) in stones" :key="`s${i}`" :cx="s.cx" :cy="s.cy" :rx="s.rx" ry="7" class="stone" />

    <!-- 小荷叶(左) -->
    <g class="pond-bob" style="transform-origin: 236px 106px; animation-duration: 6.5s">
      <ellipse cx="236" cy="106" rx="18" ry="6.5" class="lily" />
      <path d="M236 106 L251 102" class="lily-vein" stroke-width="0.8" fill="none" />
    </g>

    <!-- 飘落水面的叶子 -->
    <g class="pond-bob" style="transform-origin: 432px 100px; animation-duration: 5.2s; animation-delay: -2s">
      <path d="M432 100 C 440 98 446 103 444 110 C 438 111 431 107 432 100 Z" class="float-leaf" />
    </g>

    <!-- 荷叶 + 荷花(右), 随波轻晃 -->
    <g class="pond-bob" style="transform-origin: 652px 82px; animation-duration: 7.2s; animation-delay: -1.4s">
      <!-- 荷叶: 椭圆盘面 + 缺口 + 放射叶脉 -->
      <ellipse cx="652" cy="82" rx="34" ry="11" class="lily" />
      <path d="M652 82 L 682 76" class="lily-vein" stroke-width="1" fill="none" />
      <path d="M652 82 L 622 79 M652 82 L 628 89 M652 82 L 680 88 M652 82 L 620 83" class="lily-vein" stroke-width="0.7" fill="none" />
      <!-- 荷花 -->
      <g transform="translate(652 70)">
        <ellipse cx="-6.5" cy="0" rx="8" ry="3.4" class="lotus-petal" />
        <ellipse cx="6.5" cy="0" rx="8" ry="3.4" class="lotus-petal" />
        <ellipse
          v-for="deg in [-56, -28, 0, 28, 56]"
          :key="deg"
          cx="0"
          cy="-6.5"
          rx="3.6"
          ry="8"
          class="lotus-petal"
          :transform="`rotate(${deg})`"
        />
        <circle r="2.5" class="lotus-core" />
      </g>
    </g>
  </svg>
</template>

<script setup lang="ts">
// 涟漪滤镜移植自 garden/Ripple(feTurbulence + feDisplacementMap),
// 水波意象改用横向低频、纵向略高的基频, 位移幅度收敛到 8
import { onMounted } from 'vue'

/** 用户开启"减少动态效果"时, 停用 SMIL(以静态水纹代替) */
const reducedMotion = ref(false)
onMounted(() => {
  reducedMotion.value = window.matchMedia('(prefers-reduced-motion: reduce)').matches
})

/** 水岸轮廓(同用于水体与裁剪) */
const WATER_D = 'M0 64 C 220 38 680 38 900 64 L900 200 L0 200 Z'

/** 平静水纹线(被滤镜轻轻推挤) */
const lines = [
  { d: 'M120 92 Q 450 84 780 92', opacity: 0.4 },
  { d: 'M60 118 Q 460 110 850 118', opacity: 0.32 },
  { d: 'M160 146 Q 470 138 760 146', opacity: 0.24 },
  { d: 'M80 172 Q 450 166 820 172', opacity: 0.16 },
]

/** 天光水影(随涟漪晃动的柔和光斑) */
const glints = [
  { cx: 285, cy: 78, rx: 92 },
  { cx: 610, cy: 112, rx: 70 },
  { cx: 430, cy: 150, rx: 60 },
]

/** 扩散涟漪环 */
const rings = [
  { cx: 252, cy: 104, r: 30, dur: 5.2, begin: '-1.2s' },
  { cx: 618, cy: 94, r: 26, dur: 6.4, begin: '-3.6s' },
  { cx: 428, cy: 132, r: 22, dur: 4.6, begin: '-2.1s' },
]

/** 薄雾团 */
const mists = [
  { cx: 250, cy: 60, rx: 200 },
  { cx: 680, cy: 66, rx: 235 },
]

/** 岸石 */
const stones = [
  { cx: 92, cy: 66, rx: 22 },
  { cx: 814, cy: 70, rx: 26 },
]
</script>

<style scoped>
.pond-stop-top { stop-color: var(--note-water); }
.pond-stop-bottom { stop-color: var(--note-water-deep); }
.water-fill { fill: url(#pond-water); }
.water-line {
  stroke: var(--note-water-line);
  fill: none;
  stroke-linecap: round;
}
.water-shine { fill: var(--note-card); opacity: 0.32; }
.mist { fill: var(--note-card); opacity: 0.5; }
.stone { fill: var(--note-sub); opacity: 0.4; }
.lily { fill: var(--note-green-deep); opacity: 0.42; }
.lily-vein { stroke: var(--note-water-line); }
.lotus-petal {
  fill: var(--note-lotus);
  stroke: var(--note-water-line);
  stroke-width: 0.5;
}
.lotus-core { fill: var(--note-lotus-core); }
.float-leaf { fill: var(--note-accent); opacity: 0.6; }

/* 浮物随波轻晃 */
.pond-bob {
  animation-name: pond-bob;
  animation-timing-function: ease-in-out;
  animation-iteration-count: infinite;
  transform-box: view-box;
}

@keyframes pond-bob {
  0%, 100% { transform: translateY(0) rotate(-0.7deg); }
  50%      { transform: translateY(-3px) rotate(0.7deg); }
}

/* 薄雾横移 */
.pond-mist {
  animation: pond-mist 15s ease-in-out infinite alternate;
  transform-box: fill-box;
}

@keyframes pond-mist {
  from { transform: translateX(-22px); }
  to   { transform: translateX(22px); }
}

@media (prefers-reduced-motion: reduce) {
  .pond-bob,
  .pond-mist {
    animation: none;
  }
}
</style>
