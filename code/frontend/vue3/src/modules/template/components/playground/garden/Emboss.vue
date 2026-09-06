<template>
  <!-- 浮雕: 高光/阴影双影随光照角度游走, 凸起与凹陷只是正负之差 -->
  <div class="flex flex-col gap-4 lg:flex-row">
    <div class="flex flex-1 items-center justify-center gap-8 rounded-md border border-[var(--el-border-color-light)] bg-[#e7e2d3] p-8" :style="stageVars">
      <!-- 浮雕文字 -->
      <span class="emboss-text text-5xl font-bold text-[#e7e2d3]">GARDEN</span>
      <!-- 浮雕按钮 -->
      <button class="emboss-btn h-14 w-14 rounded-xl text-xl" :aria-label="state.raised ? '凸起按钮' : '凹陷按钮'" @click="state.raised = !state.raised">
        {{ state.raised ? '☀' : '☾' }}
      </button>
    </div>

    <!-- 控制面板 -->
    <div class="w-full shrink-0 space-y-1 lg:w-56">
      <div class="flex items-center gap-2">
        <span class="w-14 shrink-0 text-xs text-[var(--el-text-color-secondary)]">光角°</span>
        <el-slider v-model="state.angle" :min="0" :max="360" size="small" class="flex-1" />
      </div>
      <div class="flex items-center gap-2">
        <span class="w-14 shrink-0 text-xs text-[var(--el-text-color-secondary)]">深度</span>
        <el-slider v-model="state.depth" :min="1" :max="6" size="small" class="flex-1" />
      </div>
      <div class="flex items-center justify-between">
        <span class="text-xs text-[var(--el-text-color-secondary)]">凸起 / 凹陷</span>
        <el-switch v-model="state.raised" size="small" />
      </div>
      <p class="pt-1 text-xs leading-5 text-[var(--el-text-color-secondary)]">
        物体同色(文字色=背景色), 只靠两枚偏移影子塑形: 朝光侧白影、背光侧黑影;
        angle 换算成 cos/sin 偏移量即可让"太阳"绕字一周; raised 取反偏移即凹陷。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
// 浮雕(garden.bradwoods.io CSS 笔记): 双 text/box-shadow + 极坐标光照
/** 可调参数 */
const state = reactive({ angle: 315, depth: 3, raised: true })

/** 光照偏移量(dx, dy): 角度 → 单位圆坐标 */
const offset = computed(() => {
  const rad = (state.angle * Math.PI) / 180
  return { x: Math.cos(rad) * state.depth, y: Math.sin(rad) * state.depth }
})

/** 舞台级变量: 供 text/box-shadow 引用 */
const stageVars = computed(() => {
  const { x, y } = offset.value
  const sign = state.raised ? 1 : -1
  return {
    '--emb-light': `${-x * sign}px ${-y * sign}px 1px rgba(255,255,255,0.9)`,
    '--emb-dark': `${x * sign}px ${y * sign}px 1px rgba(0,0,0,0.35)`,
  }
})
</script>

<style scoped>
/* 浮雕文字: 白影在上游, 黑影在下游 */
.emboss-text {
  text-shadow: var(--emb-light), var(--emb-dark);
}

/* 浮雕按钮: inset 内凹外凸一步切换 */
.emboss-btn {
  color: #6b6455;
  background: #e7e2d3;
  box-shadow: var(--emb-light), var(--emb-dark);
  cursor: pointer;
  transition: box-shadow 0.2s;
}
</style>
