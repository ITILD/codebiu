<template>
  <!-- 换肤工坊: 用户驱动的个性化设计 —— 偏好即 CSS 变量, 即改即所见并持久化 -->
  <div class="flex flex-col gap-4 lg:flex-row">
    <!-- 演示台: 变量注入此处, 内部 Element Plus 组件同步换肤 -->
    <div class="skin-demo flex-1 rounded-md border border-[var(--el-border-color-light)] p-5" :style="skinVars">
      <p class="mb-3 text-sm text-[var(--el-text-color-regular)]">同一套组件, 不同的"皮": 你调的每一项都会即时生效。</p>
      <div class="flex flex-wrap items-center gap-3">
        <el-button type="primary">主按钮</el-button>
        <el-button>次按钮</el-button>
        <el-input v-model="demo" placeholder="输入点什么…" class="w-44" />
        <el-tag type="success" effect="light">标签</el-tag>
        <el-checkbox v-model="checked">记住我</el-checkbox>
      </div>
    </div>

    <!-- 控制面板 -->
    <div class="w-full shrink-0 space-y-2 lg:w-56">
      <div>
        <p class="mb-1 text-xs text-[var(--el-text-color-secondary)]">主题色</p>
        <div class="flex items-center gap-2">
          <button
            v-for="c in accents"
            :key="c"
            class="h-6 w-6 rounded-full border-2 transition-transform"
            :class="state.accent === c ? 'scale-110 border-[var(--el-text-color-primary)]' : 'border-transparent'"
            :style="{ background: c }"
            :aria-label="`选择主题色 ${c}`"
            @click="state.accent = c"
          />
          <el-color-picker v-model="state.accent" size="small" />
        </div>
      </div>
      <div class="flex items-center gap-2">
        <span class="w-14 shrink-0 text-xs text-[var(--el-text-color-secondary)]">圆角</span>
        <el-slider v-model="state.radius" :min="0" :max="16" size="small" class="flex-1" />
      </div>
      <el-segmented v-model="state.density" :options="densityOptions" size="small" class="w-full" />
      <el-segmented v-model="state.font" :options="fontOptions" size="small" class="w-full" />
      <p class="pt-1 text-xs leading-5 text-[var(--el-text-color-secondary)]">
        把用户偏好写进局部 CSS 变量(--el-color-primary / --el-border-radius-base…),
        Element Plus 组件无需重渲染即完成换肤; 偏好存 localStorage, 下次回来仍是"你的"界面。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
// 用户驱动 UI / 个性化(garden.bradwoods.io/notes/design/personalization):
// 偏好 → CSS 变量 → 组件即换肤; localStorage 持久化
/** 密度档 */
type Density = 'compact' | 'cozy' | 'roomy'

/** 预设主题色 */
const accents = ['#4a7c59', '#5b7fa6', '#a8762e', '#a05c5c', '#6f5b8a']

/** 密度选项 */
const densityOptions = [
  { label: '紧凑', value: 'compact' },
  { label: '舒适', value: 'cozy' },
  { label: '宽松', value: 'roomy' },
]

/** 字体选项 */
const fontOptions = [
  { label: '衬线', value: 'serif' },
  { label: '无衬线', value: 'sans' },
]

/** 偏好状态 */
const state = reactive({ accent: '#4a7c59', radius: 8, density: 'cozy' as Density, font: 'serif' })

/** 演示输入与勾选 */
const demo = ref('春植夏耘, 秋收冬藏')
const checked = ref(true)

/** 密度 → 内边距映射 */
const PAD: Record<Density, string> = { compact: '12px', cozy: '20px', roomy: '30px' }

/** 皮肤变量: 覆盖 Element Plus 的局部主题 */
const skinVars = computed(() => ({
  '--el-color-primary': state.accent,
  '--el-border-radius-base': `${state.radius}px`,
  '--el-font-family': state.font === 'serif' ? "Georgia, 'Noto Serif SC', serif" : "'Helvetica Neue', 'PingFang SC', sans-serif",
  padding: PAD[state.density],
}))

/** 持久化键 */
const KEY = 'gdn-skin-prefs'

// 载入已保存的偏好
try {
  const saved = localStorage.getItem(KEY)
  if (saved) Object.assign(state, JSON.parse(saved))
} catch {
  /* 忽略损坏数据 */
}

// 偏好变化即保存
watch(state, (v) => localStorage.setItem(KEY, JSON.stringify(v)), { deep: true })
</script>
