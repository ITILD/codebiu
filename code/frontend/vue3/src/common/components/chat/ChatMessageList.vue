<script setup lang="ts">
// 通用聊天消息列表:
// - 用户消息: 右侧苔绿气泡
// - 助手消息: 头像 + 过程区块折叠(ProcessBlock) + 富文本正文(MarkdownContent)
// - 正文操作: 复制 / 导出 Word / 导出 PDF
// - 智能滚动: 仅当用户接近底部时跟随(阅读历史时不打扰)
import { ref, nextTick, watch } from 'vue'
import { MagicStick, CopyDocument, Promotion, Document } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import MarkdownContent from './MarkdownContent.vue'
import ProcessBlock from './ProcessBlock.vue'
import { copyToClipboard, exportMarkdownToDocx, exportMarkdownToPdf } from '@/common/utils/export'
import type { DisplayMessage } from '@/common/types/chat'

interface Props {
  messages: DisplayMessage[]
  /** 流式接收中的助手消息ID(显示光标与过程区块展开态) */
  streamingMessageId?: string | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'copy', text: string): void
}>()

// 滚动容器
const scrollRef = ref<HTMLElement>()

/** 是否接近底部(120px 内) */
const isNearBottom = () => {
  const el = scrollRef.value
  if (!el) return true
  return el.scrollHeight - el.scrollTop - el.clientHeight < 120
}

/** 智能滚动: force 时强制到底, 否则仅当接近底部时跟随 */
const scrollToBottom = (force = false) => {
  nextTick(() => {
    if (!scrollRef.value) return
    if (force || isNearBottom()) scrollRef.value.scrollTop = scrollRef.value.scrollHeight
  })
}

// 消息数量/流式ID变化时尝试跟随滚动
watch(() => props.messages.length, () => scrollToBottom())
watch(
  () => props.streamingMessageId,
  (id) => { if (id) scrollToBottom(true) },
)
// 流式内容增长时跟随(长度签名变化即触发, 避免深度监听)
watch(
  () => props.messages.map((m) => `${m.content.length}-${m.blocks?.length ?? 0}`).join(','),
  () => scrollToBottom(),
)

defineExpose({ scrollToBottom })

/* ===== 消息操作 ===== */
const handleCopy = async (text: string) => {
  if (await copyToClipboard(text)) {
    ElMessage.success('已复制到剪贴板')
    emit('copy', text)
  } else {
    ElMessage.error('复制失败')
  }
}

/** 导出整条助手消息(markdown)为 Word */
const handleExportWord = async (msg: DisplayMessage) => {
  try {
    await exportMarkdownToDocx(msg.content, `AI回答-${msg.id.slice(0, 8)}`)
    ElMessage.success('Word 已导出')
  } catch (e) {
    ElMessage.error('导出失败: ' + (e instanceof Error ? e.message : '未知错误'))
  }
}

/** 导出整条助手消息(markdown)为 PDF */
const handleExportPdf = async (msg: DisplayMessage) => {
  try {
    await exportMarkdownToPdf(msg.content, `AI回答-${msg.id.slice(0, 8)}`)
    ElMessage.success('PDF 已导出')
  } catch (e) {
    ElMessage.error('导出失败: ' + (e instanceof Error ? e.message : '未知错误'))
  }
}
</script>

<template>
  <div ref="scrollRef" class="h-full overflow-y-auto overscroll-contain">
    <div class="max-w-[48rem] mx-auto w-full px-4 pt-[1.2rem] pb-6 flex flex-col gap-[1.4rem]">
      <slot name="empty" v-if="messages.length === 0" />

      <template v-for="msg in messages" :key="msg.id">
        <!-- 用户消息: 右侧苔绿气泡 -->
        <div v-if="msg.role === 'user'" class="flex justify-end">
          <div class="max-w-[85%] px-4 py-[0.6rem] rounded-note-lg rounded-br-note-sm bg-note-tint text-note-deep text-[0.9rem] leading-[1.65] whitespace-pre-wrap break-words">{{ msg.content }}</div>
        </div>

        <!-- 助手消息: 头像 + 过程区块 + 富文本正文 -->
        <div v-else class="flex gap-3">
          <div class="w-8 h-8 rounded-full bg-note-green text-white flex-center shrink-0 mt-0.5 shadow-[0_2px_8px_rgba(108,191,143,0.35)]">
            <el-icon :size="16"><MagicStick /></el-icon>
          </div>
          <div class="flex-1 min-w-0">
            <!-- 过程区块(思考/检索引用溯源, 折叠展示) -->
            <ProcessBlock
              :blocks="msg.blocks ?? []"
              :streaming="msg.id === streamingMessageId"
            />

            <!-- 等待首个 token: 思考动画 -->
            <div v-if="!msg.content && msg.id === streamingMessageId" class="cml-thinking flex items-center gap-1 py-2">
              <span class="dot inline-block w-1.5 h-1.5 rounded-full bg-note-green" /><span class="dot inline-block w-1.5 h-1.5 rounded-full bg-note-green" /><span class="dot inline-block w-1.5 h-1.5 rounded-full bg-note-green" />
            </div>

            <!-- 富文本正文(流式生成中显示光标) -->
            <div
              v-if="msg.content"
              class="cml-content"
              :class="{ 'is-streaming': msg.id === streamingMessageId }"
            >
              <MarkdownContent :content="msg.content" :block-id="msg.id" />
            </div>

            <!-- 操作: 复制 / 导出 Word / 导出 PDF -->
            <div
              v-if="msg.content && msg.id !== streamingMessageId"
              class="flex gap-1 mt-2"
            >
              <button class="inline-flex items-center gap-1 px-2 py-1 border-none rounded-note-sm bg-transparent text-note-sub text-xs cursor-pointer note-transition hover:bg-note-tint hover:text-note-green" @click="handleCopy(msg.content)">
                <el-icon :size="13"><CopyDocument /></el-icon> 复制
              </button>
              <button class="inline-flex items-center gap-1 px-2 py-1 border-none rounded-note-sm bg-transparent text-note-sub text-xs cursor-pointer note-transition hover:bg-note-tint hover:text-note-green" @click="handleExportWord(msg)">
                <el-icon :size="13"><Document /></el-icon> Word
              </button>
              <button class="inline-flex items-center gap-1 px-2 py-1 border-none rounded-note-sm bg-transparent text-note-sub text-xs cursor-pointer note-transition hover:bg-note-tint hover:text-note-green" @click="handleExportPdf(msg)">
                <el-icon :size="13"><Promotion /></el-icon> PDF
              </button>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
/* 等待首个 token 的思考动画(伪动画 + nth-child 延迟, 保留在 style) */
.cml-thinking .dot {
  animation: cml-bounce 1.2s ease-in-out infinite;
}

.cml-thinking .dot:nth-child(2) { animation-delay: 0.15s; }
.cml-thinking .dot:nth-child(3) { animation-delay: 0.3s; }

@keyframes cml-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-4px); opacity: 1; }
}

/* 流式生成中的光标(伪元素 + 动画, 保留在 style) */
.cml-content.is-streaming::after {
  content: '';
  display: inline-block;
  width: 7px;
  height: 15px;
  margin-left: 2px;
  vertical-align: text-bottom;
  background: var(--note-green, #6cbf8f);
  animation: cml-blink 1s step-end infinite;
}

@keyframes cml-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
</style>
