<template>
  <!-- 小池: 上半保留水墨风(SMIL feTurbulence 位移滤镜驱动涟漪), 下半叠 WebGL
       写实水面(fbm 波场 + 法线高光), 以渐变蒙版向下融合 —— 越向下越近越写实;
       WebGL 不可用 / 减少动态时自动回退为纯 SVG 水墨 -->
  <div class="pond-stage relative">
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

    <!-- 下景写实水面: WebGL 画布, CSS 蒙版向下渐显(与上部水墨融合) -->
    <canvas ref="glCanvas" class="pond-gl" aria-hidden="true"></canvas>
  </div>
</template>

<script setup lang="ts">
// 涟漪滤镜移植自 garden/Ripple(feTurbulence + feDisplacementMap),
// 水波意象改用横向低频、纵向略高的基频, 位移幅度收敛到 8;
// 下景写实水面为裸 WebGL1(fbm 波场 + 有限差分法线高光), 零依赖
import { onBeforeUnmount, onMounted, ref } from 'vue'

/** 用户开启"减少动态效果"时, 停用 SMIL/WebGL 动画(以静态水纹代替) */
const reducedMotion = ref(false)

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

// ===== 下景写实水面(WebGL) =====
const glCanvas = ref<HTMLCanvasElement | null>(null)
let glRaf = 0
let detachGl: (() => void) | null = null

/** 顶点着色器: 全屏四边形 + UV */
const GL_VS = `
attribute vec2 a;
varying vec2 v_uv;
void main() {
  v_uv = a * 0.5 + 0.5;
  gl_Position = vec4(a, 0.0, 1.0);
}`

/** 片元着色器: fbm 波场求高度, 有限差分取法线 → 镜面高光 + 细碎闪光;
     色彩上浅下深(近景更深更实), 波长近大远小、近景流速更缓 */
const GL_FS = `
precision mediump float;
varying vec2 v_uv;
uniform float u_time;
uniform vec3 u_shallow;
uniform vec3 u_deep;
uniform vec3 u_glint;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123); }
float noise(vec2 p) {
  vec2 i = floor(p); vec2 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x),
             mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y);
}
float fbm(vec2 p) {
  float v = 0.0; float a = 0.5;
  for (int i = 0; i < 4; i++) { v += a * noise(p); p = p * 2.03 + vec2(19.7, 7.3); a *= 0.5; }
  return v;
}
float height(vec2 uv, float t) {
  float k = mix(3.2, 1.9, uv.y);
  vec2 p = uv * vec2(k * 2.0, k);
  float h = fbm(p + vec2(t * 0.12, t * 0.05));
  h += 0.5 * fbm(p * 2.2 - vec2(t * 0.18, t * 0.07));
  h += 0.25 * fbm(p * 4.6 + vec2(t * 0.26, -t * 0.09));
  return h;
}
void main() {
  vec2 uv = v_uv;
  float t = u_time;
  float h = height(uv, t);
  float e = 0.011;
  float hx = height(uv + vec2(e, 0.0), t) - h;
  float hy = height(uv + vec2(0.0, e), t) - h;
  vec3 n = normalize(vec3(-hx * 2.6, hy * 2.6, 1.0));
  vec3 L = normalize(vec3(0.3, 0.55, 0.75));
  float spec = pow(max(dot(n, L), 0.0), 26.0);
  vec3 col = mix(u_deep, u_shallow, smoothstep(0.0, 0.92, uv.y));
  col += (h - 0.95) * 0.05;
  col += u_glint * spec * 0.4;
  float sparkle = smoothstep(0.8, 0.96, noise(uv * vec2(110.0, 46.0) + vec2(t * 0.6, t * 0.2)));
  col += u_glint * sparkle * 0.08;
  gl_FragColor = vec4(col, 1.0);
}`

/** 从 CSS 变量读取颜色(亮暗主题自适应), 解析为 0..1 RGB */
function cssRGB(name: string, fallback: [number, number, number]): [number, number, number] {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  const probe = document.createElement('canvas').getContext('2d')
  if (!probe || !raw) return fallback
  probe.fillStyle = raw
  const m = /rgba?\(([^)]+)\)/.exec(probe.fillStyle as string)
  if (m) {
    const parts = m[1].split(',').map(Number)
    return [parts[0] / 255, parts[1] / 255, parts[2] / 255]
  }
  const hex = /^#([0-9a-f]{6})$/i.exec(probe.fillStyle as string)
  if (hex) {
    const n = parseInt(hex[1], 16)
    return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255]
  }
  return fallback
}

/** 初始化 WebGL 写实水面; 失败则隐藏画布回退纯 SVG */
function setupGl() {
  const canvas = glCanvas.value
  if (!canvas) return
  const gl = canvas.getContext('webgl', { antialias: false, alpha: false })
  if (!gl) {
    canvas.style.display = 'none'
    return
  }

  const compile = (type: number, src: string) => {
    const sh = gl.createShader(type)!
    gl.shaderSource(sh, src)
    gl.compileShader(sh)
    if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(sh) || 'compile failed')
    return sh
  }
  let program: WebGLProgram
  try {
    program = gl.createProgram()!
    gl.attachShader(program, compile(gl.VERTEX_SHADER, GL_VS))
    gl.attachShader(program, compile(gl.FRAGMENT_SHADER, GL_FS))
    gl.linkProgram(program)
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error('link failed')
  } catch {
    canvas.style.display = 'none'
    return
  }
  gl.useProgram(program)

  // 全屏四边形
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer())
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW)
  const loc = gl.getAttribLocation(program, 'a')
  gl.enableVertexAttribArray(loc)
  gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0)

  const uTime = gl.getUniformLocation(program, 'u_time')
  const uShallow = gl.getUniformLocation(program, 'u_shallow')
  const uDeep = gl.getUniformLocation(program, 'u_deep')
  const uGlint = gl.getUniformLocation(program, 'u_glint')

  // 颜色取自 --note-* 变量(亮暗自适应)
  const shallowDefault: [number, number, number] = [0.81, 0.89, 0.87]
  const deepDefault: [number, number, number] = [0.64, 0.79, 0.74]
  const glint = cssRGB('--note-card', [1, 1, 1])
  const applyColors = () => {
    gl.uniform3f(uShallow, ...cssRGB('--note-water', shallowDefault))
    gl.uniform3f(uDeep, ...cssRGB('--note-water-deep', deepDefault))
    gl.uniform3f(uGlint, ...glint)
  }
  applyColors()

  // 尺寸自适应(dpr 上限 1.5, 兼顾清晰与性能)
  const resize = () => {
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5)
    const w = Math.max(1, Math.round(canvas.clientWidth * dpr))
    const h = Math.max(1, Math.round(canvas.clientHeight * dpr))
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w
      canvas.height = h
      gl.viewport(0, 0, w, h)
    }
  }
  resize()
  const ro = new ResizeObserver(resize)
  ro.observe(canvas)

  // 主题切换(html.dark)时重读颜色
  const mo = new MutationObserver(applyColors)
  mo.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })

  if (reducedMotion.value) {
    // 减少动态: 仅绘制一帧静水
    gl.uniform1f(uTime, 6)
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4)
    return
  }
  const t0 = performance.now()
  const frame = () => {
    gl.uniform1f(uTime, (performance.now() - t0) / 1000)
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4)
    glRaf = requestAnimationFrame(frame)
  }
  glRaf = requestAnimationFrame(frame)

  detachGl = () => {
    ro.disconnect()
    mo.disconnect()
  }
}

onMounted(() => {
  reducedMotion.value = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  setupGl()
})

onBeforeUnmount(() => {
  cancelAnimationFrame(glRaf)
  detachGl?.()
})
</script>

<style scoped>
/* 下景写实水面画布: 覆盖池塘下半, 蒙版向下渐显 —— 与上部水墨无缝融合 */
.pond-gl {
  position: absolute;
  left: 0;
  bottom: 0;
  width: 100%;
  height: 56%;
  display: block;
  pointer-events: none;
  -webkit-mask-image: linear-gradient(to bottom, transparent 0%, rgba(0, 0, 0, 0.28) 32%, #000 66%);
  mask-image: linear-gradient(to bottom, transparent 0%, rgba(0, 0, 0, 0.28) 32%, #000 66%);
}

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
