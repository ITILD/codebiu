<template>
  <div class="chat-container">
    <!-- 左侧历史消息列表 -->
    <div class="chat-sidebar">
      <div class="sidebar-header">
        <h3>对话历史</h3>
        <el-button type="primary" size="small" @click="createNewChat" :loading="creatingChat">
          <el-icon><Plus /></el-icon>
          新建对话
        </el-button>
      </div>
      
      <div class="chat-history">
        <!-- 加载状态 -->
        <div v-if="loadingChats" class="loading-state">
          <el-skeleton :rows="3" animated />
        </div>
        
        <!-- 空状态 -->
        <div v-else-if="chatHistory.length === 0" class="empty-state">
          <el-empty description="暂无对话记录" />
        </div>
        
        <!-- 对话列表 -->
        <div 
          v-else
          v-for="chat in chatHistory" 
          :key="chat.id"
          :class="['chat-item', { active: currentChat?.id === chat.id }]"
          @click="selectChat(chat)"
        >
          <div class="chat-title">{{ chat.title || '新对话' }}</div>
          <div class="chat-time">{{ formatTime(chat.updatedAt) }}</div>
          <div class="chat-actions">
            <el-button size="small" type="text" @click.stop="deleteChat(chat.id)" :loading="deletingChatId === chat.id">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 右侧聊天区域 -->
    <div class="chat-main">
      <!-- 聊天头部 -->
      <div class="chat-header">
        <div class="model-selector">
          <el-select 
            v-model="selectedModel" 
            placeholder="选择模型" 
            size="large"
            style="width: 200px"
          >
            <el-option
              v-for="model in availableModels"
              :key="model.id"
              :label="model.name"
              :value="model.id"
            />
          </el-select>
        </div>
        <div class="chat-title-edit">
          <el-input
            v-if="isEditingTitle"
            v-model="currentChatTitle"
            size="small"
            @blur="saveChatTitle"
            @keyup.enter="saveChatTitle"
          />
          <span v-else class="title-text" @click="startEditingTitle">
            {{ currentChatTitleComputed || '待选择' }}
          </span>
        </div>
      </div>

      <!-- 消息列表 -->
      <div class="messages-container" ref="messagesContainer">
        <!-- 空状态 -->
        <div v-if="!currentChat && !loadingMessages" class="empty-messages">
          <el-empty 
            description="选择一个对话或开始新的对话" 
            :image-size="200"
          >
            <el-button type="primary" @click="createNewChat" :loading="creatingChat">
              开始新对话
            </el-button>
          </el-empty>
        </div>
        
        <!-- 加载状态 -->
        <div v-else-if="loadingMessages" class="loading-messages">
          <div class="loading-skeletons">
            <el-skeleton :rows="3" animated style="margin-bottom: 20px;" />
            <el-skeleton :rows="2" animated style="margin-bottom: 20px;" />
            <el-skeleton :rows="3" animated />
          </div>
        </div>
        
        <!-- 消息列表 -->
        <div v-else>
          <div 
            v-for="message in currentMessages" 
            :key="message.id"
            :class="['message', message.role]"
          >
            <div class="message-avatar">
              <el-avatar 
                :size="32" 
                :src="message.role === 'user' ? userAvatar : assistantAvatar"
              >
                {{ message.role === 'user' ? '我' : 'AI' }}
              </el-avatar>
            </div>
            <div class="message-content">
              <div class="message-text">
                <div v-if="message.isStreaming" class="streaming-indicator">
                  <span class="typing-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                  </span>
                </div>
                <div v-else v-html="formatMessage(message.content)"></div>
              </div>
              <div class="message-time">{{ formatTime(message.timestamp) }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区域 -->
      <div class="input-container">
        <div class="input-wrapper">
          <el-input
            v-model="inputMessage"
            type="textarea"
            :rows="3"
            placeholder="输入您的问题..."
            :disabled="isSending"
            @keydown.enter.exact.prevent="sendMessage"
          />
          <div class="input-actions">
            <el-button 
              type="primary" 
              :loading="isSending"
              @click="sendMessage"
            >
              发送
            </el-button>
            <el-button @click="clearMessages">清空</el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete } from '@element-plus/icons-vue'
import type { ChatHistory, ChatMessage, ModelConfig } from '@/types/chat'
import { 
  sendChatMessage, 
  LocalStorageHelper,
  getChatSessions,
  createChatSession,
  updateChatSession,
  deleteChatSession,
  getChatMessages
} from '@/api/chat'
import { listModelConfigs } from '@/api/model_config'

// 响应式数据
const chatHistory = ref<ChatHistory[]>([])
const currentChat = ref<ChatHistory | null>(null)
const currentMessages = ref<ChatMessage[]>([])
const inputMessage = ref('')
const isSending = ref(false)
const selectedModel = ref('')
const availableModels = ref<ModelConfig[]>([])
const isEditingTitle = ref(false)
const currentChatTitle = ref('')
const messagesContainer = ref<HTMLElement>()

// 加载状态
const loadingChats = ref(false)
const loadingModels = ref(false)
const loadingMessages = ref(false)
const creatingChat = ref(false)
const savingTitle = ref(false)
const deletingChatId = ref<string | null>(null)

// 模拟数据
const userAvatar = 'https://cube.elemecdn.com/3/7c/3ea6beec64369c2642b92c6726f1epng.png'
const assistantAvatar = 'https://cube.elemecdn.com/0/88/03b0d39583f48206768a7534e55bcpng.png'

// 计算属性
const currentChatTitleComputed = computed({
  get: () => currentChat.value?.title || '新对话',
  set: (value) => {
    if (currentChat.value) {
      currentChat.value.title = value
    }
  }
})

// 方法
const createNewChat = async () => {
  if (creatingChat.value) return
  
  try {
    creatingChat.value = true
    
    const response = await createChatSession({ title: '新对话' })
    const newChat: ChatHistory = {
      id: response.data,
      title: '新对话',
      createdAt: new Date(),
      updatedAt: new Date(),
      messageCount: 0
    }
    
    chatHistory.value.unshift(newChat)
    selectChat(newChat)
    currentMessages.value = []
    inputMessage.value = ''
    
    // 保存到本地存储
    LocalStorageHelper.saveChatHistory(chatHistory.value)
    LocalStorageHelper.saveCurrentChat(newChat)
  } catch (error) {
    console.error('创建新对话失败:', error)
    ElMessage.error('创建新对话失败')
  } finally {
    creatingChat.value = false
  }
}

const selectChat = async (chat: ChatHistory) => {
  if (loadingMessages.value) return
  
  try {
    loadingMessages.value = true
    currentChat.value = chat
    
    // 加载该对话的消息
    const response = await getChatMessages(chat.id)
    currentMessages.value = response.data || []
    
    // 如果没有消息，添加欢迎消息
    if (currentMessages.value.length === 0) {
      currentMessages.value.push({
        id: 'welcome',
        chatId: chat.id,
        role: 'assistant',
        content: '您好！我是AI助手，有什么可以帮助您的吗？',
        timestamp: new Date()
      })
    }
    
    // 保存到本地存储
    LocalStorageHelper.saveCurrentChat(chat)
    
    // 滚动到底部
    nextTick(() => {
      scrollToBottom()
    })
  } catch (error) {
    console.error('加载对话消息失败:', error)
    // 使用模拟数据作为后备
    currentMessages.value = [
      {
        id: '1',
        chatId: chat.id,
        role: 'assistant',
        content: '您好！我是AI助手，有什么可以帮助您的吗？',
        timestamp: new Date(Date.now() - 300000)
      }
    ]
  } finally {
    loadingMessages.value = false
  }
}

const loadChatMessages = async (chatId: string) => {
  try {
    const response = await getChatMessages(chatId)
    currentMessages.value = response.data || []
    
    // 如果没有消息，添加欢迎消息
    if (currentMessages.value.length === 0) {
      currentMessages.value.push({
        id: 'welcome',
        chatId: chatId,
        role: 'assistant',
        content: '您好！我是AI助手，有什么可以帮助您的吗？',
        timestamp: new Date()
      })
    }
  } catch (error) {
    console.error('加载消息失败:', error)
    // 使用模拟数据作为后备
    currentMessages.value = [
      {
        id: '1',
        chatId: chatId,
        role: 'assistant',
        content: '您好！我是AI助手，有什么可以帮助您的吗？',
        timestamp: new Date(Date.now() - 300000)
      }
    ]
  }
}

const sendMessage = async () => {
  if (!inputMessage.value.trim() || !selectedModel.value) {
    ElMessage.warning('请选择模型并输入消息')
    return
  }

  if (!currentChat.value) {
    await createNewChat()
    if (!currentChat.value) return
  }

  const userMessage: ChatMessage = {
    id: Date.now().toString(),
    chatId: currentChat.value!.id,
    role: 'user',
    content: inputMessage.value,
    timestamp: new Date()
  }

  currentMessages.value.push(userMessage)
  
  const assistantMessage: ChatMessage = {
    id: (Date.now() + 1).toString(),
    chatId: currentChat.value!.id,
    role: 'assistant',
    content: '',
    timestamp: new Date(),
    isStreaming: true
  }

  currentMessages.value.push(assistantMessage)
  
  const messageToSend = inputMessage.value
  inputMessage.value = ''
  isSending.value = true

  try {
    // 调用真实的API
    const response = await sendChatMessage({
      modelId: selectedModel.value,
      messages: [userMessage],
      streaming: false
    })
    
    assistantMessage.content = response.data.content
    assistantMessage.isStreaming = false
    assistantMessage.timestamp = new Date()
    
    // 更新聊天历史
    if (currentChat.value) {
      currentChat.value.updatedAt = new Date()
      currentChat.value.messageCount = currentMessages.value.length
      
      // 更新会话标题（如果是第一个消息）
      if (currentMessages.value.length === 2) {
        currentChat.value.title = messageToSend.slice(0, 20) + '...'
        await updateChatSession(currentChat.value.id, { title: currentChat.value.title })
      }
    }
    
    // 保存到本地存储
    LocalStorageHelper.saveChatHistory(chatHistory.value)
    
  } catch (error) {
    console.error('发送消息失败:', error)
    assistantMessage.content = '抱歉，消息发送失败，请稍后重试。'
    assistantMessage.isStreaming = false
    ElMessage.error('消息发送失败')
  } finally {
    isSending.value = false
    scrollToBottom()
  }

  scrollToBottom()
}

const generateAIResponse = (message: string): string => {
  const responses = [
    `我理解您的问题"${message}"。这是一个很好的问题！让我为您详细解答...`,
    `关于"${message}"，我可以从以下几个方面为您分析：首先...`,
    `感谢您的提问！对于"${message}"，我的理解是...`,
    `您提到的"${message}"很有意义。让我为您提供一些相关信息...`
  ]
  return responses[Math.floor(Math.random() * responses.length)]
}

const clearMessages = () => {
  ElMessageBox.confirm('确定要清空当前对话的所有消息吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(() => {
    currentMessages.value = []
    ElMessage.success('消息已清空')
  })
}

const deleteChat = async (chatId: string) => {
  try {
    await ElMessageBox.confirm('确定要删除这个对话吗？删除后将无法恢复', '确认删除', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    deletingChatId.value = chatId
    
    // 调用API删除对话
    await deleteChatSession(chatId)
    
    chatHistory.value = chatHistory.value.filter(chat => chat.id !== chatId)
    
    if (currentChat.value?.id === chatId) {
      currentChat.value = null
      currentMessages.value = []
      LocalStorageHelper.saveCurrentChat(null)
    }
    
    // 保存到本地存储
    LocalStorageHelper.saveChatHistory(chatHistory.value)
    
    ElMessage.success('对话已删除')
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除对话失败:', error)
      ElMessage.error('删除对话失败')
    }
  } finally {
    deletingChatId.value = null
  }
}

const startEditingTitle = () => {
  isEditingTitle.value = true
  nextTick(() => {
    const input = document.querySelector('.chat-title-edit input') as HTMLInputElement
    input?.focus()
  })
}

const saveChatTitle = async () => {
  isEditingTitle.value = false
  if (currentChat.value && currentChatTitle.value.trim() && !savingTitle.value) {
    const newTitle = currentChatTitle.value.trim()
    currentChat.value.title = newTitle
    
    try {
      savingTitle.value = true
      // 调用API更新会话标题
      await updateChatSession(currentChat.value.id, { title: newTitle })
      
      // 更新本地存储
      LocalStorageHelper.saveChatHistory(chatHistory.value)
      
      ElMessage.success('标题已更新')
    } catch (error) {
      console.error('更新标题失败:', error)
      ElMessage.error('更新标题失败')
    } finally {
      savingTitle.value = false
    }
  }
}

const formatTime = (date: Date) => {
  return new Date(date).toLocaleTimeString('zh-CN', { 
    hour: '2-digit', 
    minute: '2-digit' 
  })
}

const formatMessage = (content: string) => {
  // 简单的Markdown格式处理
  return content
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/\n/g, '<br>')
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

// 生命周期
onMounted(async () => {
  try {
    loadingModels.value = true
    loadingChats.value = true
    
    // 加载模型配置
    const modelResponse = await listModelConfigs({ page: 1, size: 50 })
    availableModels.value = modelResponse.data.items.map((item: any) => ({
      id: item.id,
      name: item.name || item.model,
      type: item.model_type || 'chat'
    }))
    
    // 如果没有模型配置，使用模拟数据
    if (availableModels.value.length === 0) {
      availableModels.value = [
        { id: 'qwen', name: '通义千问', type: 'chat' },
        { id: 'gpt', name: 'GPT-4', type: 'chat' },
        { id: 'claude', name: 'Claude', type: 'chat' }
      ]
    }
    
    loadingModels.value = false
    
    // 设置选中的模型
    const savedModel = LocalStorageHelper.loadSelectedModel()
    selectedModel.value = savedModel || (availableModels.value[0]?.id || '')
    
    // 加载聊天历史
    try {
      const chatResponse = await getChatSessions()
      chatHistory.value = chatResponse.data || []
    } catch (error) {
      console.error('加载聊天历史失败，使用本地存储:', error)
      chatHistory.value = LocalStorageHelper.loadChatHistory()
    }
    
    loadingChats.value = false
    
    // 加载当前选中的聊天
    const savedChat = LocalStorageHelper.loadCurrentChat()
    if (savedChat && chatHistory.value.some(chat => chat.id === savedChat.id)) {
      selectChat(savedChat)
    } else if (chatHistory.value.length > 0) {
      selectChat(chatHistory.value[0])
    }
    
  } catch (error) {
    console.error('初始化失败:', error)
    ElMessage.error('初始化失败，请刷新页面重试')
    loadingModels.value = false
    loadingChats.value = false
  }
})

// 监听消息变化，自动滚动到底部
watch(currentMessages, () => {
  scrollToBottom()
}, { deep: true })

// 监听选中的模型变化，保存到本地存储
watch(selectedModel, (newModel) => {
  if (newModel) {
    LocalStorageHelper.saveSelectedModel(newModel)
  }
})
</script>

<style scoped>
.chat-container {
  display: flex;
  height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.chat-sidebar {
  width: 320px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-right: 1px solid rgba(255, 255, 255, 0.2);
  display: flex;
  flex-direction: column;
  box-shadow: 2px 0 10px rgba(0, 0, 0, 0.1);
}

.sidebar-header {
  padding: 24px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(255, 255, 255, 0.8);
}

.sidebar-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #2c3e50;
}

.chat-history {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.chat-item {
  padding: 16px 24px;
  cursor: pointer;
  position: relative;
  transition: all 0.3s ease;
  border-left: 4px solid transparent;
}

.chat-item:hover {
  background: rgba(103, 126, 234, 0.1);
  transform: translateX(4px);
}

.chat-item.active {
  background: linear-gradient(135deg, rgba(103, 126, 234, 0.15), rgba(118, 75, 162, 0.1));
  border-left-color: #667eea;
  box-shadow: inset 0 0 20px rgba(103, 126, 234, 0.1);
}

.chat-title {
  font-weight: 500;
  margin-bottom: 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #2c3e50;
  font-size: 14px;
}

.chat-time {
  font-size: 12px;
  color: #7f8c8d;
}

.chat-actions {
  position: absolute;
  top: 12px;
  right: 12px;
  opacity: 0;
  transition: all 0.3s ease;
}

.chat-item:hover .chat-actions {
  opacity: 1;
  transform: scale(1.1);
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  box-shadow: -2px 0 10px rgba(0, 0, 0, 0.1);
}

.chat-header {
  padding: 20px 32px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.1);
  display: flex;
  align-items: center;
  gap: 24px;
  background: rgba(255, 255, 255, 0.8);
}

.model-selector {
  flex-shrink: 0;
}

.chat-title-edit {
  flex: 1;
}

.title-text {
  font-size: 20px;
  font-weight: 600;
  cursor: pointer;
  padding: 8px 12px;
  border-radius: 8px;
  transition: all 0.3s ease;
  color: #2c3e50;
  background: transparent;
}

.title-text:hover {
  background: rgba(103, 126, 234, 0.1);
  box-shadow: 0 2px 8px rgba(103, 126, 234, 0.2);
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 32px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.9), rgba(248, 249, 250, 0.8));
}

.message {
  display: flex;
  margin-bottom: 24px;
  gap: 16px;
  animation: fadeInUp 0.5s ease;
}

.message.user {
  flex-direction: row-reverse;
}

.message-avatar {
  flex-shrink: 0;
}

.message-content {
  max-width: 70%;
  min-width: 200px;
}

.message.user .message-content {
  text-align: right;
}

.message-text {
  background: linear-gradient(135deg, #f8f9fa, #e9ecef);
  padding: 16px 20px;
  border-radius: 20px;
  line-height: 1.6;
  word-wrap: break-word;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.5);
  position: relative;
}

.message-text::before {
  content: '';
  position: absolute;
  top: 12px;
  left: -8px;
  width: 16px;
  height: 16px;
  background: inherit;
  transform: rotate(45deg);
  border-left: 1px solid rgba(255, 255, 255, 0.5);
  border-bottom: 1px solid rgba(255, 255, 255, 0.5);
}

.message.user .message-text {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
  border: none;
}

.message.user .message-text::before {
  left: auto;
  right: -8px;
  border: none;
  background: linear-gradient(135deg, #667eea, #764ba2);
}

.message-time {
  font-size: 12px;
  color: #7f8c8d;
  margin-top: 8px;
  font-weight: 300;
}

.input-container {
  padding: 24px 32px;
  border-top: 1px solid rgba(0, 0, 0, 0.1);
  background: rgba(255, 255, 255, 0.9);
}

.input-wrapper {
  position: relative;
  max-width: 800px;
  margin: 0 auto;
}

.input-actions {
  margin-top: 16px;
  text-align: right;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.streaming-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
}

.typing-dots {
  display: inline-flex;
  gap: 4px;
}

.typing-dots span {
  width: 8px;
  height: 8px;
  background: #667eea;
  border-radius: 50%;
  animation: typing 1.4s infinite ease-in-out;
}

.typing-dots span:nth-child(1) { animation-delay: -0.32s; }
.typing-dots span:nth-child(2) { animation-delay: -0.16s; }

@keyframes typing {
  0%, 80%, 100% { 
    transform: scale(0.8); 
    opacity: 0.5; 
  }
  40% { 
    transform: scale(1.2); 
    opacity: 1; 
  }
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 滚动条样式 */
.messages-container::-webkit-scrollbar {
  width: 6px;
}

.messages-container::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.1);
  border-radius: 3px;
}

.messages-container::-webkit-scrollbar-thumb {
  background: rgba(103, 126, 234, 0.5);
  border-radius: 3px;
}

.messages-container::-webkit-scrollbar-thumb:hover {
  background: rgba(103, 126, 234, 0.7);
}

.chat-history::-webkit-scrollbar {
  width: 4px;
}

.chat-history::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.05);
}

.chat-history::-webkit-scrollbar-thumb {
  background: rgba(103, 126, 234, 0.3);
  border-radius: 2px;
}

.chat-history::-webkit-scrollbar-thumb:hover {
  background: rgba(103, 126, 234, 0.5);
}

/* 加载状态和空状态样式 */
.loading-state {
  padding: 20px;
}

.empty-state {
  padding: 40px 20px;
  text-align: center;
}

.empty-messages {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  min-height: 400px;
}

.loading-messages {
  padding: 40px 20px;
}

.loading-skeletons {
  max-width: 600px;
  margin: 0 auto;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .chat-sidebar {
    width: 280px;
    position: absolute;
    left: -280px;
    z-index: 1000;
    transition: left 0.3s ease;
  }
  
  .chat-sidebar.open {
    left: 0;
  }
  
  .message-content {
    max-width: 85%;
  }
  
  .chat-header {
    padding: 16px 20px;
  }
  
  .messages-container {
    padding: 20px;
  }
  
  .empty-messages {
    min-height: 300px;
  }
}
</style>