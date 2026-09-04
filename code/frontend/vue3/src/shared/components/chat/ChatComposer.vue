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
</script>

<template>
  <div class="cc-card">
    <el-input
      :model-value="modelValue"
      type="textarea"
      :autosize="{ minRows: 1, maxRows: 8 }"
      :placeholder="placeholder"
      :disabled="disabled"
      @update:model-value="onInput"
      @keydown="onKeydown"
    />
    <div class="cc-footer">
      <span class="cc-hint">{{ hint || 'Enter 发送 · Shift+Enter 换行' }}</span>
      <!-- 停止生成 / 发送 -->
      <el-tooltip v-if="isSending" content="停止生成" placement="top">
        <button class="cc-btn stop" @click="handleStop">
          <el-icon :size="16"><VideoPause /></el-icon>
        </button>
      </el-tooltip>
      <el-tooltip v-else content="发送" placement="top">
        <button class="cc-btn" :class="{ enabled: canSend }" :disabled="!canSend" @click="handleSend">
          <el-icon :size="16"><Promotion /></el-icon>
        </button>
      </el-tooltip>
    </div>
  </div>
</template>

<style scoped>
/* 悬浮纸片输入卡 */
.cc-card {
  border-radius: 1rem;
  background: var(--el-bg-color, #fff);
  border: 1px solid var(--note-border, #e2e8e3);
  box-shadow: 0 2px 12px rgba(108, 191, 143, 0.14);
  transition: border-color 0.2s;
}

.cc-card:focus-within {
  border-color: var(--note-green, #6cbf8f);
}

/* textarea 无边框融入卡片 */
.cc-card :deep(.el-textarea__inner) {
  box-shadow: none !important;
  background: transparent;
  padding: 12px 14px 4px;
  font-size: 0.9rem;
  line-height: 1.6;
}

.cc-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 10px 10px;
}

.cc-hint {
  font-size: 12px;
  color: var(--note-sub, #6b7f6e);
}

.cc-btn {
  width: 36px;
  height: 36px;
  border-radius: 9999px;
  border: 1px solid var(--note-border, #e2e8e3);
  background: var(--note-card, #fff);
  color: var(--note-sub, #6b7f6e);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
}

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
  border-color: #e6a23c;
  color: #e6a23c;
}

.cc-btn.stop:hover {
  background: #fdf6ec;
}

.cc-btn:disabled {
  background: var(--note-tint, #e7f3e9);
  border-color: var(--note-border, #e2e8e3);
  color: var(--note-sub, #6b7f6e);
  cursor: not-allowed;
  box-shadow: none;
}
</style>
