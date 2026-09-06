<template>
  <!-- 全息投影: 单色化 + RGB 色散 + 扫描线 + 浮动闪烁, 全部由 CSS 叠层完成 -->
  <div class="flex flex-col gap-4 lg:flex-row">
    <div class="relative h-64 flex-1 overflow-hidden rounded-md border border-[#1d2a26] bg-[#0d1512]" :style="stageVars">
      <div class="holo-float absolute inset-8">
        <img :src="mainPhoto" alt="全息投影演示" class="holo-img h-full w-full rounded object-cover" loading="lazy" decoding="async" />
        <!-- 扫描线层: multiply 压出 CRT 横纹 -->
        <div class="holo-lines pointer-events-none absolute inset-0 rounded" />
        <!-- 掠过的高光带 + 闪烁 -->
        <div class="holo-glint pointer-events-none absolute inset-x-0 h-2/5" :style="{ opacity: state.flicker }" />
      </div>
      <span class="pointer-events-none absolute bottom-2 left-3 text-xs text-[#9ec7b8]">悬停暂停浮动, 感受扫描线与色散</span>
    </div>

    <!-- 控制面板 -->
    <div class="w-full shrink-0 space-y-1 lg:w-56">
      <div class="flex items-center gap-2">
        <span class="w-14 shrink-0 text-xs text-[var(--el-text-color-secondary)]">线距px</span>
        <el-slider v-model="state.gap" :min="3" :max="9" size="small" class="flex-1" />
      </div>
      <div class="flex items-center gap-2">
        <span class="w-14 shrink-0 text-xs text-[var(--el-text-color-secondary)]">色相s</span>
        <el-slider v-model="state.hueDur" :min="2" :max="12" :step="0.5" size="small" class="flex-1" />
      </div>
      <div class="flex items-center gap-2">
        <span class="w-14 shrink-0 text-xs text-[var(--el-text-color-secondary)]">闪烁</span>
        <el-slider v-model="state.flicker" :min="0" :max="1" :step="0.05" size="small" class="flex-1" />
      </div>
      <p class="pt-1 text-xs leading-5 text-[var(--el-text-color-secondary)]">
        sepia + hue-rotate 把图压成单色荧光; 两枚反向 drop-shadow 制造红青色散;
        repeating-linear-gradient 是扫描线, 一条渐变高光带循环掠过即是"信号扫过"。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
// 纯 CSS 全息效果(garden.bradwoods.io/notes/svg/hologram): 滤镜单色化 + 叠层混合
import { mainPhoto } from './texture'

/** 可调参数 */
const state = reactive({ gap: 4, hueDur: 6, flicker: 0.5 })

/** 舞台级 CSS 变量: 供 scoped keyframes/背景引用 */
const stageVars = computed(() => ({
  '--holo-gap': `${state.gap}px`,
  '--holo-hue-dur': `${state.hueDur}s`,
}))
</script>

<style scoped>
/* 浮动 + 轻微透视俯仰, 悬停暂停 */
.holo-float {
  perspective: 600px;
  animation: holo-drift 4.5s ease-in-out infinite alternate;
}
.holo-float:hover {
  animation-play-state: paused;
}

/* 单色荧光 + 红青色散: drop-shadow 在不透明图像边缘露出偏移的彩色剪影 */
.holo-img {
  filter:
    sepia(1) hue-rotate(130deg) saturate(4) brightness(1.05)
    drop-shadow(2px 0 rgba(255, 60, 120, 0.35))
    drop-shadow(-2px 0 rgba(60, 255, 240, 0.35));
  animation: holo-hue var(--holo-hue-dur) linear infinite;
}

/* 扫描线: 1px 暗纹按变量间距平铺 */
.holo-lines {
  background: repeating-linear-gradient(0deg, rgba(0, 0, 0, 0.28) 0 1px, transparent 1px var(--holo-gap));
  mix-blend-mode: multiply;
}

/* 高光带: 自上而下循环掠过 */
.holo-glint {
  background: linear-gradient(to bottom, transparent, rgba(214, 255, 244, 0.55), transparent);
  animation: holo-scan 2.6s ease-in-out infinite;
}

@keyframes holo-drift {
  from { transform: translateY(0) rotateX(0deg); }
  to { transform: translateY(-9px) rotateX(5deg); }
}

@keyframes holo-hue {
  from { filter: sepia(1) hue-rotate(115deg) saturate(4) brightness(1.05) drop-shadow(2px 0 rgba(255, 60, 120, 0.35)) drop-shadow(-2px 0 rgba(60, 255, 240, 0.35)); }
  to { filter: sepia(1) hue-rotate(160deg) saturate(4) brightness(1.05) drop-shadow(2px 0 rgba(255, 60, 120, 0.35)) drop-shadow(-2px 0 rgba(60, 255, 240, 0.35)); }
}

@keyframes holo-scan {
  from { transform: translateY(-60%); }
  to { transform: translateY(260%); }
}
</style>
