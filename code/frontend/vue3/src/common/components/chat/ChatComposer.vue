<script setup lang="ts">
// 聊天输入区: 自适应高度 textarea + Enter发送/Shift+Enter换行 + 发送/停止按钮
import { Promotion, VideoPause } from '@element-plus/icons-vue'

interface Props {
  /** 输入内容(v-model) */
  modelValue: string
  /** 占位提示 */
  placeholder?: string
  /** 是否正在生成(显示停止按钮) */
  isSending?: boolean
  /** 是否禁用输入 */
  disabled?: boolean
  /** 底部提示文案 */
  hint?: string
}

const props = withDefaults(defineProps<Props>(), {
  placeholder: '输入你的问题...',
  isSending: false,
  disabled: false,
  hint: '',
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'send'): void
  (e: 'stop'): void
}>()

const canSend = computed(
  () => !!props.modelValue.trim() && !props.isSending && !props.disabled,
)

/** Enter 发送, Shift+Enter 换行 */
const onKeydown = (e: Event | KeyboardEvent) => {
  const ke = e as KeyboardEvent
  if (ke.key === 'Enter' && !ke.shiftKey && !ke.isComposing) {
    ke.preventDefault()
    if (canSend.value) emit('send')
  }
}

const handleSend = () => {
  if (canSend.value) emit('send')
}

const handleStop = () => emit('stop')

const onInput = (value: string) => emit('update:modelValue', value)

// ===== 多行检测: 文字到达按钮区域(需要换行)时, 按键自动下移一行 =====
const inputRef = ref<{ textarea?: HTMLTextAreaElement } | null>(null)
const mirrorRef = ref<HTMLElement | null>(null)
const isMultiline = ref(false)
// 行布局下的可用输入宽度缓存(避免两种布局间来回抖动)
let rowAvail = 0

// ===== 高度自适应: 手动计算, 不用 EP autosize =====
// autosize 在挂载时测量, 早于 scoped 样式注入(padding 未生效), 会漏算上下 padding 导致空内容就溢出出滚动条
const resizeInput = () => {
  const el = inputRef.value?.textarea
  if (!el) return
  // 清除 EP 挂载时(样式注入前)误算的内联 min-height, 交由 CSS 的 1 行高度(35px)兜底
  el.style.minHeight = ''
  // 先归零再读 scrollHeight, 拿到内容真实需要的高度(含 padding)
  el.style.height = 'auto'
  const h = el.scrollHeight
  const maxH = parseFloat(getComputedStyle(el).maxHeight) || 150
  el.style.height = `${h}px`
  // 未到封顶行数时隐藏溢出(防亚像素误差产生幻影滚动条); 封顶后才允许滚动
  el.style.overflowY = h > maxH ? 'auto' : 'hidden'
}

/** 同步布局状态: 有显式换行或实测换行行数 > 1 → 按键下移 */
const syncMultiline = () => {
  const el = inputRef.value?.textarea
  const mirror = mirrorRef.value
  if (!el || !mirror) return
  const cs = getComputedStyle(el)
  const text = props.modelValue
  // 行布局时刷新可用宽度缓存; 已下移时沿用缓存, 同一段文本状态保持稳定不抖动
  if (!isMultiline.value) {
    rowAvail = el.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight)
  }
  if (text.includes('\n')) {
    isMultiline.value = true
    return
  }
  if (rowAvail <= 0) return
  // 隐藏镜像元素按行布局宽度实测换行行数(与浏览器实际渲染一致)
  mirror.style.width = `${rowAvail}px`
  mirror.style.fontFamily = cs.fontFamily
  mirror.style.fontSize = cs.fontSize
  mirror.style.fontWeight = cs.fontWeight
  mirror.style.fontStyle = cs.fontStyle
  mirror.style.letterSpacing = cs.letterSpacing
  mirror.textContent = text
  const lh = parseFloat(cs.lineHeight) || 21
  isMultiline.value = mirror.offsetHeight / lh > 1.5
}

watch(
  () => props.modelValue,
  () => nextTick(() => {
    resizeInput()
    syncMultiline()
  }),
  { immediate: true },
)
onMounted(() => {
  resizeInput()
  syncMultiline()
  // 尺寸变化时重新评估: 覆盖窗口缩放/样式延迟注入(此时 padding 生效会引起尺寸变化)等场景
  const el = inputRef.value?.textarea
  if (el && typeof ResizeObserver !== 'undefined') {
    new ResizeObserver(() => {
      resizeInput()
      syncMultiline()
    }).observe(el)
  }
})
</script>

<template>
  <div class="cc-card relative rounded-note-lg bg-[var(--el-bg-color,#fff)] shadow-note transition-shadow duration-200 px-2.5 py-2">
    <!-- 同行布局: 输入在左控制区在右; 文字多到换行时按键自动下移一行(stacked 复合态样式保留在 scoped style) -->
    <div class="cc-row flex items-center gap-1.5" :class="{ stacked: isMultiline }">
      <el-input
        ref="inputRef"
        :model-value="modelValue"
        type="textarea"
        :rows="1"
        :placeholder="placeholder"
        :disabled="disabled"
        resize="none"
        @update:model-value="onInput"
        @keydown="onKeydown"
      />
      <div class="cc-side flex items-center gap-2 shrink-0">
        <div class="cc-toolbar flex items-center gap-1.5 min-w-0">
          <slot name="toolbar">
            <span class="text-xs text-note-sub whitespace-nowrap">{{ hint || 'Enter 发送 · Shift+Enter 换行' }}</span>
          </slot>
        </div>
        <!-- 停止生成 / 发送 -->
        <el-tooltip v-if="isSending" content="停止生成" placement="top">
          <button class="cc-btn stop flex items-center justify-center w-9 h-9 rounded-full border border-transparent bg-note-card text-note-sub cursor-pointer note-transition shadow-[0_0_0_1px_var(--note-edge-soft,rgba(107,158,120,0.16))]" @click="handleStop">
            <el-icon :size="16"><VideoPause /></el-icon>
          </button>
        </el-tooltip>
        <el-tooltip v-else content="发送" placement="top">
          <button class="cc-btn flex items-center justify-center w-9 h-9 rounded-full border border-transparent bg-note-card text-note-sub cursor-pointer note-transition shadow-[0_0_0_1px_var(--note-edge-soft,rgba(107,158,120,0.16))]" :class="{ enabled: canSend }" :disabled="!canSend" @click="handleSend">
            <el-icon :size="16"><Promotion /></el-icon>
          </button>
        </el-tooltip>
      </div>
    </div>
    <!-- 行宽镜像(隐藏): 按行布局宽度实测文本换行行数, 决定按键是否下移 -->
    <div ref="mirrorRef" class="cc-mirror absolute top-0 left-0 invisible pointer-events-none whitespace-pre-wrap break-words text-[0.9rem] leading-[23px]" aria-hidden="true"></div>
  </div>
</template>

<style scoped>
/* 聚焦: 光晕环收拢变亮, 提示输入中(状态选择器, 保留在 style) */
.cc-card:focus-within {
  box-shadow: 0 0 0 2px var(--note-edge-soft, rgba(107, 158, 120, 0.16)), 0 6px 20px -6px var(--note-glow, rgba(107, 158, 120, 0.22));
}

/* 聚焦时的淡渐变光晕: 几乎不可见的流动微光(伪元素 + 动画, 保留在 style) */
.cc-card::before {
  content: '';
  position: absolute;
  inset: -1px;
  border-radius: inherit;
  pointer-events: none;
  background: linear-gradient(
    120deg,
    rgba(108, 191, 143, 0) 0%,
    rgba(108, 191, 143, 0.1) 25%,
    rgba(160, 214, 183, 0.14) 50%,
    rgba(108, 191, 143, 0.1) 75%,
    rgba(108, 191, 143, 0) 100%
  );
  background-size: 250% 100%;
  opacity: 0;
  transition: opacity 0.5s ease;
  animation: cc-glow-flow 4s linear infinite;
  z-index: 0;
}

.cc-card:focus-within::before {
  opacity: 1;
}

/* 光晕之上内容保持可交互(子元素选择器, 保留在 style) */
.cc-card > * {
  position: relative;
  z-index: 1;
}

@keyframes cc-glow-flow {
  0% { background-position: 100% 0; }
  100% { background-position: -150% 0; }
}

/* 同行布局下 el-textarea 占满剩余宽度(子元素选择器, 保留在 style) */
.cc-row > .el-textarea {
  flex: 1;
  min-width: 0;
}

/* 多行布局: 输入占满整行, 按键下移一行(动态态 + 子元素联动, 保留在 style) */
.cc-row.stacked {
  flex-direction: column;
  align-items: stretch;
  gap: 4px;
}

.cc-row.stacked .cc-side {
  justify-content: space-between;
}

/* textarea 无边框融入卡片; 行高用整数像素, 避免自适应高度出现亚像素溢出(幻影滚动条) */
/* 高度范围 1~6 行(23px 行高 + 上下 12px padding → 35px/150px), 实际高度由 JS 按内容设置 */
.cc-card :deep(.el-textarea__inner) {
  box-shadow: none !important;
  background: transparent;
  padding: 6px 8px;
  font-size: 0.9rem;
  line-height: 23px;
  border-radius: 0.75rem;
  min-height: 35px;
  max-height: 150px;
}

/* 行宽镜像(隐藏): z 层压到卡片之下(负 z-index, 保留在 style) */
.cc-mirror {
  z-index: -1;
}

.cc-card :deep(.el-textarea__inner)::placeholder {
  color: var(--note-sub, #6b7f6e);
  opacity: 0.7;
}

/* 胶囊形下拉选择器(与思考模式按钮统一风格): :deep 穿透, 保留在 style */
.cc-toolbar :deep(.el-select) {
  width: 150px;
}

.cc-toolbar :deep(.el-select__wrapper) {
  border-radius: 9999px;
  background: var(--note-tint, #e7f3e9);
  box-shadow: none !important;
  border: 1px solid transparent;
  min-height: 30px;
  padding: 2px 12px;
  font-size: 12px;
  transition: all 0.2s;
}

.cc-toolbar :deep(.el-select__wrapper:hover),
.cc-toolbar :deep(.el-select__wrapper.is-focused) {
  border-color: var(--note-border-green, #a9c9b1);
  background: var(--el-bg-color, #fff);
}

.cc-toolbar :deep(.el-select__placeholder) {
  color: var(--note-sub, #6b7f6e);
}

.cc-toolbar :deep(.el-select__selected-item) {
  color: var(--note-green, #6cbf8f);
}

.cc-toolbar :deep(.el-select .el-tag) {
  border-radius: 9999px;
  background: transparent;
  border-color: var(--note-green, #6cbf8f);
  color: var(--note-green, #6cbf8f);
}

/* 发送/停止按钮状态样式(enabled/stop/disabled, scoped 特异性覆盖 uno 基础类, 保留在 style) */
.cc-btn.enabled {
  background: var(--note-green, #6cbf8f);
  border-color: var(--note-green, #6cbf8f);
  color: #fff;
  box-shadow: 0 2px 10px rgba(108, 191, 143, 0.4);
}

.cc-btn.enabled:hover {
  opacity: 0.9;
  transform: scale(0.96);
}

.cc-btn.stop {
  border-color: var(--note-seal, #ad563e);
  color: var(--note-seal, #ad563e);
}

.cc-btn.stop:hover {
  /* 暖色微底: 由朱砂色混纸底调出, 暗色模式下自动收敛 */
  background: color-mix(in srgb, var(--note-seal, #ad563e) 12%, var(--note-card, #fff));
}

.cc-btn:disabled {
  background: var(--note-tint, #e7f3e9);
  border-color: var(--note-border, #e2e8e3);
  color: var(--note-sub, #6b7f6e);
  cursor: not-allowed;
  box-shadow: none;
}
</style>

<style>
/* ---- textarea 滚动条(全局作用域, 避免 scoped 穿透编译差异导致样式失效) ---- */
/* 标准属性(Chromium 121+/Firefox 均支持): 细条无上下箭头; 设置后自动覆盖下方 webkit 规则 */
/* 旧 Chromium 不认识标准属性会忽略, 回退到下方 webkit 自定义规则 */
.cc-card .el-textarea__inner {
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--note-green, #6cbf8f) 40%, transparent) transparent;
}

/* 仅当内容超过6行可滚动时才出现; 细窄圆角、无上下箭头 */
.cc-card .el-textarea__inner::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

/* 显式隐藏上下左右箭头按钮 */
.cc-card .el-textarea__inner::-webkit-scrollbar-button {
  display: none;
  width: 0;
  height: 0;
}

.cc-card .el-textarea__inner::-webkit-scrollbar-thumb {
  background: color-mix(in srgb, var(--note-green, #6cbf8f) 25%, transparent);
  border-radius: 9999px;
}

.cc-card .el-textarea__inner::-webkit-scrollbar-thumb:hover {
  background: color-mix(in srgb, var(--note-green, #6cbf8f) 45%, transparent);
}

.cc-card .el-textarea__inner::-webkit-scrollbar-track,
.cc-card .el-textarea__inner::-webkit-scrollbar-corner {
  background: transparent;
}
</style>
