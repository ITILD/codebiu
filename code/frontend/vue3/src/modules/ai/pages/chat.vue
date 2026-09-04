<template>
  <div flex flex-col h-app w-full bg-note-paper overflow-hidden>
    <!-- 通用 AI 聊天: 模型选择 + 富文本消息流(markdown/公式/图表) + 可中断流式 -->
    <!-- 顶部栏: 模型选择 + 清空对话 -->
    <header
      flex flex-wrap items-center gap-3 px-3 md:px-5 py-2.5 border-b border-note
      class="bg-note-soft/70" backdrop-blur
    >
      <LLMSelect
        v-model:model-id="model_id"
        :model-list="tableData"
        :disabled="isSending"
        @change="handleModelChange"
      />
      <el-button
        text
        type="danger"
        :disabled="messages.length === 0 || isSending"
        @click="clearMessages"
      >
        清空对话
      </el-button>
    </header>

    <!-- 消息流 -->
    <ChatMessageList
      ref="messageListRef"
      :messages="messages"
      :streaming-message-id="streamingMessageId"
      flex-1
    >
      <!-- 空状态: 问候 + 建议问题卡片 -->
      <template #empty>
        <div class="min-h-[60%]" flex flex-col items-center justify-center py-8 text-center>
          <div w-16 h-16 rounded-2xl bg-note-tint flex-center shadow-note mb-4>
            <el-icon :size="30" text-note-green><ChatDotRound /></el-icon>
          </div>
          <h2 text-xl font-bold text-note>AI 助手</h2>
          <p mt-1 text-sm text-note-sub>选择模型，支持 Markdown、公式与图表渲染</p>
          <div grid grid-cols-1 sm:grid-cols-2 gap-2.5 mt-8 w-full max-w-lg>
            <button
              v-for="s in suggestions" :key="s.label"
              flex items-center gap-3 p-3.5 rounded-xl border border-note bg-note-card text-left
              hover:border-note-green hover:shadow-note hover:-translate-y-0.5 transition-all
              @click="applySuggestion(s.question)"
            >
              <div w-8 h-8 rounded-lg bg-note-tint flex-center shrink-0>
                <el-icon :size="16" text-note-green><component :is="s.icon" /></el-icon>
              </div>
              <div min-w-0>
                <div text-sm font-medium text-note>{{ s.label }}</div>
                <div text-xs text-note-sub truncate>{{ s.question }}</div>
              </div>
            </button>
          </div>
        </div>
      </template>
    </ChatMessageList>

    <!-- 输入区 -->
    <div px-3 md:px-4 pb-3 md:pb-4>
      <div max-w-3xl mx-auto>
        <ChatComposer
          v-model="inputMessage"
          :is-sending="isSending"
          :disabled="!model_id"
          :hint="model_id ? '' : '请先在上方选择模型'"
          @send="handleSend"
          @stop="handleStop"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ChatDotRound, EditPen, DataAnalysis, Cpu, List } from '@element-plus/icons-vue'
import type { PaginationParams, PaginationResponse } from '@/common/types/common'
import type { ModelConfig } from '../types/model_config'
import type { ChatMessageWithBlocks, MessageBlock } from '@/common/types/chat'
import { StreamEventType } from '@/common/types/chat'
import { listModelConfigs } from '../api/model_config'
import { sendChatMessageStream } from '../api/chat'
import LLMSelect from '../components/LLMSelect.vue'
import ChatMessageList from '@/common/components/chat/ChatMessageList.vue'
import ChatComposer from '@/common/components/chat/ChatComposer.vue'

// ===== 模型配置 =====
const pagination = ref<PaginationParams>({ page: 1, size: 50 })
const model_id = ref('')
const tableData = ref<ModelConfig[]>([])

// ===== 聊天状态 =====
const messages = ref<ChatMessageWithBlocks[]>([])
const inputMessage = ref('')
const isSending = ref(false)
const streamingMessageId = ref<string | null>(null)
const messageListRef = ref<InstanceType<typeof ChatMessageList>>()

// 停止生成(中止 SSE)
let abortController: AbortController | null = null
let stopRequested = false

// 空状态建议问题(点击即发送)
const suggestions = [
  { label: '解释概念', question: '用通俗的语言解释一下什么是向量数据库', icon: markRaw(Cpu) },
  { label: '总结归纳', question: '帮我总结最近的工作进展，输出为要点列表', icon: markRaw(List) },
  { label: '撰写文稿', question: '帮我起草一份项目周报模板', icon: markRaw(EditPen) },
  { label: '数据分析', question: '用 mermaid 画一个用户注册流程图', icon: markRaw(DataAnalysis) },
]

const handleModelChange = (modelId: string) => {
  console.log('模型已切换至:', modelId)
}

// 清空对话
const clearMessages = () => {
  messages.value = []
  streamingMessageId.value = null
}

// 点击建议问题直接发送
const applySuggestion = (question: string) => {
  inputMessage.value = question
  handleSend()
}

// ===== 流式事件分组 =====
// 按 (stream_event_type + node_name) 把过程内容(推理等)累积到 blocks; answer 归入正文
let currentBlock: MessageBlock | null = null

const appendEvent = (msg: ChatMessageWithBlocks, event: {
  content?: string | null
  node_name?: string | null
  stream_event_type?: string | null
}) => {
  const content = event.content ?? ''
  if (!content) return
  const type = event.stream_event_type
  // 正式回答(或未分类事件) → 正文
  if (!type || type === StreamEventType.ANSWER) {
    msg.content += content
    currentBlock = null
    return
  }
  // 过程内容(推理过程等) → 过程区块
  if (
    !currentBlock
    || currentBlock.stream_event_type !== type
    || currentBlock.node_name !== (event.node_name ?? '')
  ) {
    currentBlock = {
      id: `blk-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      node_name: event.node_name ?? '',
      type: 'process',
      content: '',
      stream_event_type: type,
    }
    msg.blocks = [...(msg.blocks ?? []), currentBlock]
  }
  currentBlock.content += content
}

// ===== 发送/停止 =====
const handleSend = async () => {
  const message = inputMessage.value.trim()
  if (!message || !model_id.value || isSending.value) return

  // 追加用户消息
  messages.value.push({
    id: `${Date.now()}`,
    chatId: '',
    role: 'user',
    content: message,
    timestamp: new Date(),
  })
  inputMessage.value = ''

  // 助手消息占位(流式填充正文与过程区块)
  const assistantMsg = reactive<ChatMessageWithBlocks>({
    id: `${Date.now() + 1}`,
    chatId: '',
    role: 'assistant',
    content: '',
    timestamp: new Date(),
    isStreaming: true,
    blocks: [],
  })
  messages.value.push(assistantMsg)
  streamingMessageId.value = assistantMsg.id
  isSending.value = true
  stopRequested = false
  abortController = null
  currentBlock = null

  // 结束收尾(幂等)
  const finishStream = () => {
    assistantMsg.isStreaming = false
    streamingMessageId.value = null
    isSending.value = false
    if (!assistantMsg.content && !assistantMsg.blocks?.length) {
      assistantMsg.content = stopRequested ? '（已停止生成）' : '（未收到回复，请重试）'
    }
    messageListRef.value?.scrollToBottom(true)
  }

  try {
    await sendChatMessageStream(
      {
        model_id: model_id.value,
        // 携带历史上下文(排除流式中的占位消息)
        messages: messages.value
          .filter((m) => !m.isStreaming)
          .map((m) => ({ role: m.role as 'user' | 'assistant' | 'system', content: m.content })),
        streaming: true,
      },
      // 流式内容回调(兼容旧签名, 正文由 onEvent 统一处理)
      () => {},
      // 错误回调
      (error: string) => {
        if (!stopRequested) assistantMsg.content = `> [错误] ${error}`
        finishStream()
      },
      // 完成回调
      () => finishStream(),
      // 中止控制器(供"停止生成")
      (controller: AbortController) => {
        abortController = controller
      },
      // 完整事件回调: 按事件类型分组(正文/推理过程)
      (event) => appendEvent(assistantMsg, event),
    )
  } catch (error) {
    console.error('发送消息失败:', error)
    if (!stopRequested) assistantMsg.content = '发送失败，请重试'
    finishStream()
  }
}

// 停止生成(中止 SSE 请求)
const handleStop = () => {
  stopRequested = true
  abortController?.abort()
}

// 加载模型配置列表(默认选中第一个)
onMounted(async () => {
  // 仅加载对话类模型配置(过滤掉 asr/tts/ocr 等其它类型)
  const response: PaginationResponse<ModelConfig> = await listModelConfigs({
    ...pagination.value,
    model_type: 'chat',
  } as PaginationParams)
  tableData.value = response.items
  if (response.items.length > 0) {
    model_id.value = response.items[0].id
  }
})
</script>
