<script setup lang="ts">
// 用户交互卡片(AG-UI CUSTOM rag.interaction):
// - clarify 澄清: 意图分析判定信息不足, 请求用户补充关键信息
// - knowledge_gap 知识缺口: 检索零命中, 用户可补充内容/直接AI回答/换问法重检
// 已响应后收起为紧凑态(问题 + 响应摘要), 历史恢复时同样只读展示
import { computed, ref } from 'vue'
import { ChatDotRound, Warning, ArrowRight } from '@element-plus/icons-vue'
import type {
  InteractionKind,
  InteractionResponsePayload,
  MessageInteraction,
} from '@/common/types/agui'

interface Props {
  /** 交互卡片快照(spec + 响应状态) */
  interaction: MessageInteraction
  /** 是否禁用输入(流式进行中) */
  disabled?: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'respond', payload: InteractionResponsePayload): void
}>()

const kind = computed<InteractionKind>(() => props.interaction.spec.kind)
const isClarify = computed(() => kind.value === 'clarify')

/** knowledge_gap 当前选中的选项值(supplement/answer_directly/rephrase) */
const selectedOption = ref('')
const textValue = ref('')
const submitting = ref(false)

/** 是否需要文本输入才可提交 */
const needText = computed(() => {
  if (isClarify.value) return false
  return selectedOption.value === 'supplement' || selectedOption.value === 'rephrase'
})

/** 提交按钮禁用条件 */
const cannotSubmit = computed(() => {
  if (props.disabled || props.interaction.responded || submitting.value) return true
  if (!isClarify.value && !selectedOption.value) return true
  if (needText.value && !textValue.value.trim()) return true
  return false
})

const doSubmit = () => {
  if (cannotSubmit.value) return
  submitting.value = true
  const payload: InteractionResponsePayload = isClarify.value
    ? {
        interaction_id: props.interaction.spec.interaction_id,
        action: 'submit',
        value: textValue.value.trim(),
      }
    : {
        interaction_id: props.interaction.spec.interaction_id,
        action: selectedOption.value as InteractionResponsePayload['action'],
        value: textValue.value.trim() || undefined,
      }
  emit('respond', payload)
}

/** 跳过(仅澄清类: 不补充, 基于现有信息回答) */
const doSkip = () => {
  if (props.disabled || props.interaction.responded || submitting.value) return
  submitting.value = true
  emit('respond', {
    interaction_id: props.interaction.spec.interaction_id,
    action: 'skip',
  })
}

/** 响应摘要(已响应态展示) */
const responseSummary = computed(() => {
  const r = props.interaction.response
  if (!r) return '已响应'
  if (r.value) return r.value
  const labels: Record<string, string> = {
    skip: '跳过补充，直接回答',
    submit: '已补充信息',
    supplement: '已补充内容',
    answer_directly: '直接用 AI 知识回答',
    rephrase: '换个问法重新检索',
  }
  return labels[r.action] ?? r.action
})
</script>

<template>
  <!-- 已响应: 紧凑只读态 -->
  <div
    v-if="interaction.responded"
    class="mb-2.5 rounded-note-md bg-note-soft px-3 py-2 flex items-start gap-[5px] text-[12px] leading-[1.65]"
  >
    <el-icon :size="12" class="shrink-0 mt-[3px] text-note-sub opacity-70">
      <component :is="isClarify ? ChatDotRound : Warning" />
    </el-icon>
    <span class="shrink-0 text-note-deep opacity-[.72]">{{ interaction.spec.title }}：</span>
    <span class="flex-1 min-w-0 whitespace-pre-wrap break-words opacity-[.8]">{{ responseSummary }}</span>
  </div>

  <!-- 待响应: 交互卡片 -->
  <div
    v-else
    class="mb-2.5 rounded-note-md bg-note-soft border border-solid"
    style="border-color: var(--note-tint, #e7f3e9)"
  >
    <!-- 标题行 -->
    <div class="flex items-center gap-1.5 px-3 pt-2.5 pb-1 text-[13px] font-medium text-note-deep">
      <el-icon :size="14" class="text-note-green" :class="isClarify ? '' : 'text-[#d99a2b]'">
        <component :is="isClarify ? ChatDotRound : Warning" />
      </el-icon>
      <span>{{ interaction.spec.title }}</span>
    </div>

    <!-- 问题 -->
    <div class="px-3 pb-2 text-[13px] leading-[1.7] text-[color:var(--el-text-color-regular,#444)] whitespace-pre-wrap">
      {{ interaction.spec.question }}
    </div>

    <!-- knowledge_gap: 选项列表 -->
    <div v-if="!isClarify && interaction.spec.options.length" class="px-3 pb-2 flex flex-col gap-1.5">
      <button
        v-for="opt in interaction.spec.options"
        :key="opt.value"
        class="opt-btn flex items-center gap-2 px-2.5 py-2 border border-solid rounded-note-sm bg-transparent text-left cursor-pointer note-transition"
        :class="{ selected: selectedOption === opt.value }"
        :disabled="disabled || submitting"
        @click="selectedOption = opt.value"
      >
        <el-icon :size="13" class="shrink-0 mt-px"><ArrowRight /></el-icon>
        <span class="min-w-0">
          <span class="block text-[13px] leading-snug font-medium">{{ opt.label }}</span>
          <span v-if="opt.description" class="block text-[11px] leading-snug opacity-[.68]">{{ opt.description }}</span>
        </span>
      </button>
    </div>

    <!-- 文本输入(澄清类必显示; knowledge_gap 选择后显示) -->
    <div
      v-if="interaction.spec.allow_text && (isClarify || selectedOption)"
      class="px-3 pb-2"
    >
      <el-input
        v-model="textValue"
        type="textarea"
        :rows="isClarify ? 2 : 4"
        resize="none"
        :placeholder="interaction.spec.text_placeholder || '请输入补充内容'"
        :disabled="disabled || submitting"
        maxlength="8000"
        show-word-limit
      />
    </div>

    <!-- 操作 -->
    <div class="flex items-center gap-2 px-3 pb-2.5">
      <button
        class="px-3 py-1.5 border-none rounded-note-sm bg-note-green text-white text-[13px] font-medium cursor-pointer note-transition hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="cannotSubmit"
        @click="doSubmit"
      >
        {{ submitting ? '已提交' : '提交' }}
      </button>
      <button
        v-if="isClarify"
        class="px-3 py-1.5 border-none rounded-note-sm bg-transparent text-note-sub text-[13px] cursor-pointer note-transition hover:bg-note-tint hover:text-note-green disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="disabled || interaction.responded || submitting"
        @click="doSkip"
      >
        跳过，直接回答
      </button>
    </div>
  </div>
</template>

<style scoped>
/* 选项按钮复合态(:hover/.selected 改边框与底色, UnoCSS 无法等价表达) */
.opt-btn {
  border-color: var(--note-tint, #e7f3e9);
  color: var(--el-text-color-regular, #444);
}

.opt-btn:not(:disabled):hover {
  border-color: var(--note-green, #6cbf8f);
  background: var(--note-tint, #e7f3e9);
}

.opt-btn.selected {
  border-color: var(--note-green, #6cbf8f);
  background: var(--note-tint, #e7f3e9);
  color: var(--note-green-deep, #3f7a52);
}
</style>
