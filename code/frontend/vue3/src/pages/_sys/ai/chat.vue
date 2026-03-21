<template>
  <div flex flex-col h-screen w-full bg-gray-50>
    <!-- 顶部模型选择栏 -->
    <div p-4 border-b bg-white shadow-sm>
      <div flex items-center gap-4>
        <div flex items-center gap-2>
          <span text-sm font-medium text-gray-600>模型:</span>
          <el-select
            v-model="model_id"
            placeholder="选择模型"
            style="width: 240px"
            :disabled="isSending"
          >
            <el-option
              v-for="item in tableData"
              :key="item.id"
              :label="item.model"
              :value="item.id"
            />
          </el-select>
        </div>
        <el-button
          text
          type="danger"
          :disabled="messages.length === 0"
          @click="clearMessages"
        >
          清空对话
        </el-button>
      </div>
    </div>

    <!-- 对话列表 -->
    <div
      ref="chatContainer"
      flex-1
      flex
      flex-col
      gap-4
      overflow-y-auto
      p-4
      scroll-smooth
    >
      <div
        v-for="message in messages"
        :key="message.id"
        flex
        :class="message.role === 'user' ? 'justify-end' : 'justify-start'"
      >
        <div
          max-w-70%
          p-4
          rounded-lg
          shadow-sm
          :class="[
            message.role === 'user'
              ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white'
              : 'bg-white text-gray-800 border border-gray-200'
          ]"
        >
          <div
            text-sm
            leading-relaxed
            whitespace-pre-wrap
            break-words
            :class="message.isStreaming ? 'animate-pulse' : ''"
          >
            {{ message.content }}
            <span
              v-if="message.isStreaming"
              class="inline-block w-2 h-5 ml-1 bg-current opacity-70 animate-blink"
            ></span>
          </div>
          <div
            text-xs
            mt-2
            opacity-70
            :class="message.role === 'user' ? 'text-blue-100' : 'text-gray-400'"
          >
            {{ formatTime(message.timestamp) }}
          </div>
        </div>
      </div>

      <!-- 空状态提示 -->
      <div
        v-if="messages.length === 0"
        flex
        flex-col
        items-center
        justify-center
        h-full
        text-gray-400
      >
        <div text-6xl mb-4>💬</div>
        <div text-lg>开始对话吧</div>
        <div text-sm>选择一个模型，输入消息开始聊天</div>
      </div>
    </div>

    <!-- 输入框和发送按钮 -->
    <div flex gap-3 p-4 border-t bg-white shadow-sm>
      <el-input
        v-model="inputMessage"
        type="textarea"
        :rows="3"
        placeholder="输入消息... (Enter 发送, Shift+Enter 换行)"
        @keydown.enter.exact.prevent="handleSend"
        @keydown.enter.shift.prevent
        :disabled="isSending"
      />
      <el-button
        type="primary"
        :loading="isSending"
        :disabled="!inputMessage.trim() || !model_id"
        @click="handleSend"
        class="self-end"
      >
        {{ isSending ? '生成中' : '发送' }}
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  type PaginationParams,
  type PaginationResponse,
} from '@/types/common';
import type { ModelConfig } from '@/types/model_config';
import type { ChatMessage } from '@/types/chat';
import { listModelConfigs } from '@/api/model_config'
import { sendChatMessageStream } from '@/api/chat'
import { triggerRef } from 'vue'

// 分页参数
const pagination = ref<PaginationParams>({
  page: 1,
  size: 10
})

const model_id = ref('')

// 表格数据
const tableData = ref<ModelConfig[]>([])
// 消息列表
const messages = ref<ChatMessage[]>([])
// 输入消息
const inputMessage = ref('')
// 发送状态
const isSending = ref(false)
// 聊天容器引用
const chatContainer = ref<HTMLElement>()
// 滚动节流控制
let scrollAnimationFrame: number | null = null

// 格式化时间
const formatTime = (timestamp: Date) => {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

// 滚动到底部（优化版）
const scrollToBottom = () => {
  if (scrollAnimationFrame) {
    cancelAnimationFrame(scrollAnimationFrame)
  }

  scrollAnimationFrame = requestAnimationFrame(() => {
    nextTick(() => {
      if (chatContainer.value) {
        chatContainer.value.scrollTop = chatContainer.value.scrollHeight
      }
      scrollAnimationFrame = null
    })
  })
}

// 清空对话
const clearMessages = () => {
  messages.value = []
}

// 发送消息（优化版）
const handleSend = async () => {
  const message = inputMessage.value.trim()
  if (!message || !model_id.value || isSending.value) {
    return
  }

  // 添加用户消息
  const userMessage: ChatMessage = {
    id: Date.now().toString(),
    chatId: '',
    role: 'user',
    content: message,
    timestamp: new Date()
  }
  messages.value.push(userMessage)

  // 清空输入框
  inputMessage.value = ''

  // 滚动到底部
  scrollToBottom()

  // 创建助手消息占位符 用 reactive 包装,实时流式显示
const assistantMessage = reactive<ChatMessage>({
  id: (Date.now() + 1).toString(),
  chatId: '',
  role: 'assistant',
  content: '',
  timestamp: new Date(),
  isStreaming: true
})
  messages.value.push(assistantMessage)

  // 设置发送状态
  isSending.value = true

  try {
    // 调用流式聊天接口
    await sendChatMessageStream(
      {
        model_id: model_id.value,
        messages: messages.value.filter(m => !m.isStreaming).map(m => ({
          role: m.role,
          content: m.content
        })),
        streaming: true
      },
      // 接收数据块回调（立即更新）
      (content: string) => {
        // 立即更新内容
        assistantMessage.content += content

        // // 强制触发响应式更新
        // triggerRef(messages)

        // 立即滚动到底部，不使用节流
        nextTick(() => {
          scrollToBottom()
        })
      },
      // 错误回调
      (error: string) => {
        assistantMessage.content = `错误: ${error}`
        assistantMessage.isStreaming = false
        isSending.value = false
      },
      // 完成回调
      () => {
        assistantMessage.isStreaming = false
        isSending.value = false

        // 确保最后滚动到底部
        nextTick(() => {
          scrollToBottom()
        })
      }
    )
  } catch (error) {
    console.error('发送消息失败:', error)
    assistantMessage.content = '发送失败，请重试'
    assistantMessage.isStreaming = false
    isSending.value = false
  }
}

// 初始化编辑器
onMounted(async () => {
  // 获取模型配置列表
  const params = {
    ...pagination.value,
  }

  const response: PaginationResponse<ModelConfig> = await listModelConfigs(params)
  tableData.value = response.items
  if (response.items.length > 0) {
    model_id.value = response.items[0].id
  }
})

// 清理定时器和动画帧
onBeforeUnmount(() => {
  if (scrollAnimationFrame) {
    cancelAnimationFrame(scrollAnimationFrame)
    scrollAnimationFrame = null
  }
})
</script>

<style scoped>
/* 光标闪烁动画 */
@keyframes blink {
  0%, 50% {
    opacity: 1;
  }
  51%, 100% {
    opacity: 0;
  }
}

.animate-blink {
  animation: blink 1s infinite;
}
</style>
