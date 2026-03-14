<template>
  <div flex flex-col h-screen w-full>
    <div p-4 border-b>
      <el-select v-model="model_id" placeholder="Select" style="width: 240px">
        <el-option
          v-for="item in tableData"
          :key="item.id"
          :label="item.model"
          :value="item.id"
        />
      </el-select>
    </div>
  <!-- 对话列表 -->
  <div flex-1 flex flex-col gap-4 overflow-y-auto p-4>
    <div
      v-for="message in messages"
      :key="message.id"
      flex
      :class="message.role === 'user' ? 'justify-end' : 'justify-start'"
    >
      <div
        max-w-70%
        p-3
        rounded-lg
        :class="message.role === 'user' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-800'"
      >
        <div text-sm>{{ message.content }}</div>
        <div text-xs mt-1 opacity-70>{{ formatTime(message.timestamp) }}</div>
      </div>
    </div>
  </div>

  <!--输入信息和发送按钮 -->
  <div flex gap-2 p-4 border-t>
    <el-input
      v-model="inputMessage"
      type="textarea"
      :rows="2"
      placeholder="输入消息..."
      @keydown.enter.prevent="handleSend"
    />
    <el-button
      type="primary"
      :loading="isSending"
      @click="handleSend"
    >
      发送
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
import { sendChatMessage } from '@/api/chat'
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

// 格式化时间
const formatTime = (timestamp: Date) => {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

// 发送消息
const handleSend = async () => {

}

// 初始化编辑器
onMounted(async () => {
  // 获取模型配置列表
      const params = {
      ...pagination.value,
    }

    const response: PaginationResponse<ModelConfig> = await listModelConfigs(params)
    tableData.value = response.items
    model_id.value = response.items[0].id
})






</script>

<style scoped></style>
