<template>
  <!-- CSS 3D: 父级 perspective 提供透视, 卡片随鼠标 rotateX/rotateY, 内容分层 translateZ -->
  <div class="flex flex-col gap-4 lg:flex-row lg:items-center">
    <!-- 3D 舞台 -->
    <div
      class="relative flex flex-1 items-center justify-center overflow-hidden rounded-md bg-[var(--el-bg-color-page)] py-12 [perspective:900px]"
      @mousemove="onMove"
      @mouseleave="onLeave"
    >
      <div
        class="relative w-64 rounded-lg border border-[var(--el-border-color-light)] bg-[var(--el-bg-color)] p-5 shadow-xl will-change-transform [transform-style:preserve-3d]"
        :style="cardStyle"
      >
        <!-- 顶层浮动小方块: preserve-3d 旋转立方体 -->
        <div class="absolute right-5 top-5 [transform:translateZ(46px)]">
          <div class="cube">
            <span v-for="f in 6" :key="f" class="face" :class="`face-${f}`" />
          </div>
        </div>
        <!-- 分层内容: 不同 translateZ 产生纵深视差 -->
        <svg class="[transform:translateZ(60px)]" width="52" height="52" viewBox="0 0 56 56" fill="none" aria-hidden="true">
          <path d="M28 50 V30" stroke="var(--el-color-primary)" stroke-width="3" stroke-linecap="round" />
          <path d="M28 32 C28 20 18 14 8 14 C8 26 18 32 28 32 Z" fill="var(--el-color-primary-light-5)" />
          <path d="M28 32 C28 24 34 20 44 20 C44 28 38 32 28 32 Z" fill="var(--el-color-primary)" />
        </svg>
        <h4 class="mt-3 text-base font-bold text-[var(--el-text-color-primary)] [transform:translateZ(34px)]">透视卡片</h4>
        <p class="mt-1 text-xs leading-5 text-[var(--el-text-color-secondary)] [transform:translateZ(22px)]">
          父级 perspective 提供三维空间，标题、图标与文字位于不同深度(translateZ)，移动鼠标感受视差与高光。
        </p>
        <!-- 随鼠标移动的高光 -->
        <div
          class="pointer-events-none absolute inset-0 rounded-lg"
          :style="{ background: `radial-gradient(circle at ${gx}% ${gy}%, rgba(255, 255, 255, 0.35), transparent 55%)` }"
        />
      </div>
    </div>

    <!-- 控制面板 -->
    <div class="w-full shrink-0 space-y-3 lg:w-56">
      <div class="flex items-center gap-2">
        <span class="w-16 shrink-0 text-xs text-[var(--el-text-color-secondary)]">倾斜幅度</span>
        <el-slider v-model="maxTilt" :min="5" :max="30" size="small" class="flex-1" />
      </div>
      <p class="text-xs leading-5 text-[var(--el-text-color-secondary)]">
        perspective 值越小透视越强烈; preserve-3d 让孙级元素也留在三维空间中(否则被拍扁到父级平面)。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
// CSS 3D(garden.bradwoods.io/notes/css/3d):
// perspective / perspective-origin / translate3d / rotateX·Y / preserve-3d 综合演示

/** 最大倾斜角度(度) */
const maxTilt = ref(14)

/** 绕 X 轴旋转 */
const rx = ref(0)

/** 绕 Y 轴旋转 */
const ry = ref(0)

/** 高光位置 x(%) */
const gx = ref(50)

/** 高光位置 y(%) */
const gy = ref(50)

/** 是否悬停中(控制过渡时长) */
const hovering = ref(false)

/** 卡片变换样式 */
const cardStyle = computed(() => ({
  transform: `rotateX(${rx.value}deg) rotateY(${ry.value}deg)`,
  transition: hovering.value ? 'transform 0.06s linear' : 'transform 0.5s ease',
}))

/** 鼠标移动: 倾斜卡片并移动高光 */
function onMove(e: MouseEvent) {
  const el = e.currentTarget as HTMLElement
  const r = el.getBoundingClientRect()
  const nx = (e.clientX - r.left) / r.width
  const ny = (e.clientY - r.top) / r.height
  hovering.value = true
  rx.value = -(ny - 0.5) * 2 * maxTilt.value
  ry.value = (nx - 0.5) * 2 * maxTilt.value
  gx.value = nx * 100
  gy.value = ny * 100
}

/** 鼠标离开: 弹回原位 */
function onLeave() {
  hovering.value = false
  rx.value = 0
  ry.value = 0
  gx.value = 50
  gy.value = 50
}
</script>

<style scoped>
/* 旋转立方体: 六面绕轴平移拼合 */
.cube {
  position: relative;
  width: 40px;
  height: 40px;
  transform-style: preserve-3d;
  animation: cube-spin 10s linear infinite;
}

.face {
  position: absolute;
  inset: 0;
  border: 1px solid var(--el-color-primary);
  background: hsla(140, 30%, 45%, 0.12);
}

.face-1 { transform: translateZ(20px); }
.face-2 { transform: rotateY(180deg) translateZ(20px); }
.face-3 { transform: rotateY(90deg) translateZ(20px); }
.face-4 { transform: rotateY(-90deg) translateZ(20px); }
.face-5 { transform: rotateX(90deg) translateZ(20px); }
.face-6 { transform: rotateX(-90deg) translateZ(20px); }

@keyframes cube-spin {
  from { transform: rotateX(-18deg) rotateY(0deg); }
  to { transform: rotateX(-18deg) rotateY(360deg); }
}
</style>
