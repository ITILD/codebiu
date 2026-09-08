<template>
  <div flex flex-col h-app w-full bg-note-paper overflow-hidden>
    <div flex flex-1 min-h-0 w-full>
    <!-- 智能体对话: 可收起会话列表 + 居中消息流(过程区块) + 悬浮输入卡 -->
    <!-- 移动端抽屉遮罩 -->
    <Transition name="fade">
      <div v-if="sidebarOpen" fixed inset-0 z-20 class="bg-black/30" md:hidden @click="sidebarOpen = false" />
    </Transition>

    <!-- 会话列表(桌面默认常驻可收起, 移动端侧滑抽屉) -->
    <aside
      fixed md:static inset-y-0 left-0 z-30 w-72 shrink-0 flex flex-col bg-note-soft border-r border-note
      transition-all duration-300
      :class="sidebarOpen ? 'translate-x-0 md:ml-0' : '-translate-x-full md:-ml-72'"
    >
      <!-- 新建 + 搜索 -->
      <div p-3 space-y-2.5>
        <button
          class="active:scale-[0.98]"
          flex items-center justify-center gap-1.5 w-full py-2.5 rounded-xl bg-note-green text-white text-sm font-medium
          shadow-note hover:opacity-90 transition-all
          @click="handleCreateConversation"
        >
          <el-icon :size="16"><Plus /></el-icon>
          新建对话
        </button>
        <el-input v-model="searchText" placeholder="搜索对话" size="small" clearable>
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </div>

      <!-- 分组会话列表(今天/昨天/7天内/更早) -->
      <div flex-1 overflow-y-auto px-2 pb-3>
        <template v-for="group in groupedConversations" :key="group.label">
          <div px-3 pt-3 pb-1 text-xs font-medium text-note-sub>{{ group.label }}</div>
          <div
            v-for="conv in group.items" :key="conv.id"
            flex items-center gap-2 px-3 py-2.5 rounded-xl cursor-pointer group transition-colors
            :class="conv.id === currentConversationId
              ? 'bg-note-tint text-note shadow-note'
              : 'text-note-sub hover:bg-note-tint/60'"
            @click="selectConversation(conv.id)"
          >
            <el-icon :size="15" shrink-0 opacity-70><ChatDotRound /></el-icon>
            <span flex-1 truncate text-sm>{{ conv.title || '新对话' }}</span>
            <!-- 删除 -->
            <button
              op-0 group-hover:op-100 shrink-0 p-1 rounded-md class="hover:bg-red-500/15" hover:text-red-500 transition
              title="删除对话" @click.stop="handleDeleteConversation(conv)"
            >
              <el-icon :size="14"><Delete /></el-icon>
            </button>
          </div>
        </template>
        <!-- 空列表 -->
        <div v-if="groupedConversations.length === 0" py-14 text-center text-sm text-note-sub>
          {{ searchText ? '未找到相关对话' : '暂无对话' }}
        </div>
      </div>

      <!-- 次级管理入口(小字低调, 不抢历史列表) -->
      <div px-3 py-2.5 border-t border-note space-y-0.5>
        <RouterLink
          to="/agent/manage"
          flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-note-sub
          hover:bg-note-tint hover:text-note-green transition-colors
        >
          <el-icon :size="13"><MagicStick /></el-icon>
          智能体管理
        </RouterLink>
      </div>
    </aside>

    <!-- 右侧聊天区域 -->
    <section flex-1 flex flex-col min-w-0 relative>
      <!-- 顶部栏: 侧栏开关 + 当前会话标题 -->
      <header
        flex items-center gap-2 px-3 md:px-5 py-2.5 border-b border-note
        class="bg-note-soft/70" backdrop-blur
      >
        <button
          rounded-full p-2 text-note hover:bg-note-tint transition
          title="切换会话列表" @click="sidebarOpen = !sidebarOpen"
        >
          <el-icon :size="20"><Menu /></el-icon>
        </button>
        <h2 v-if="currentConversation" flex-1 min-w-0 truncate text-sm font-medium text-note m-0>
          {{ currentConversation.title || '新对话' }}
        </h2>
      </header>

      <!-- 消息流: 居中阅读宽度(过程区块 + 富文本) -->
      <ChatMessageList
        ref="messageListRef"
        :messages="messages"
        :streaming-message-id="streamingMessageId"
        flex-1
      >
        <!-- 空状态: 问候 + 智能体选择卡片 -->
        <template #empty>
          <div class="min-h-[60%]" flex flex-col items-center justify-center py-8 text-center>
            <div w-16 h-16 rounded-2xl bg-note-tint flex-center shadow-note mb-4>
              <el-icon :size="30" text-note-green><MagicStick /></el-icon>
            </div>
            <h2 text-xl font-bold text-note>智能体对话</h2>
            <p mt-1 text-sm text-note-sub>选择一个智能体开始对话，也可在管理页创建自己的智能体</p>
            <div grid grid-cols-1 sm:grid-cols-2 gap-2.5 mt-8 w-full max-w-lg>
              <button
                v-for="a in builtinAgents" :key="a.id"
                flex items-center gap-3 p-3.5 rounded-xl border text-left transition-all
                :class="selectedAgentId === a.id
                  ? 'border-note-green bg-note-tint shadow-note'
                  : 'border-note bg-note-card hover:border-note-green hover:shadow-note hover:-translate-y-0.5'"
                @click="selectedAgentId = a.id"
              >
                <div w-8 h-8 rounded-lg bg-note-tint flex-center shrink-0>
                  <el-icon :size="16" text-note-green><MagicStick /></el-icon>
                </div>
                <div min-w-0>
                  <div text-sm font-medium text-note>{{ a.name }}</div>
                  <div text-xs text-note-sub truncate>{{ a.description }}</div>
                </div>
              </button>
            </div>
          </div>
        </template>
      </ChatMessageList>

      <!-- 输入区: 悬浮卡片式输入框(卡片内底部为智能体选择) -->
      <div px-3 md:px-4 pb-3 md:pb-4>
        <div max-w-3xl mx-auto>
          <ChatComposer
            v-model="inputMessage"
            :is-sending="isSending"
            @send="handleSend"
            @stop="handleStop"
          >
            <template #toolbar>
              <el-select
                v-model="selectedAgentId" clearable
                class="w-40 sm:w-56" size="small" placeholder="选择智能体" :disabled="isSending"
              >
                <el-option
                  v-for="a in agents" :key="a.id"
                  :label="a.name"
                  :value="a.id"
                >
                  <div flex items-center justify-between gap-2>
                    <span>{{ a.name }}</span>
                    <el-tag v-if="a.is_builtin" size="small" effect="plain" type="success">内置</el-tag>
                  </div>
                </el-option>
              </el-select>
            </template>
          </ChatComposer>
        </div>
        <p text-center text-xs text-note-sub mt-2>内容由 AI 生成，请注意甄别</p>
      </div>
    </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Plus, Search, Delete, Menu, MagicStick, ChatDotRound } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { usePermission } from '@/common/composables/usePermission'
import {
  listMyAgentConversations,
  getAgentConversation,
  createAgentConversation,
  deleteAgentConversation,
  listAgentConversationMessages,
  listAgents,
  sendAgentChatStream,
} from '../api/agent'
import ChatMessageList from '@/common/components/chat/ChatMessageList.vue'
import ChatComposer from '@/common/components/chat/ChatComposer.vue'
import { StreamEventType } from '@/common/types/chat'
import type { MessageBlock } from '@/common/types/chat'
import type { ChatMessage } from '../../rag/types'
import type { Agent, AgentConversation } from '../types'

const router = useRouter()
const { hasPerm } = usePermission()

// ===== 智能体 =====
const agents = ref<Agent[]>([])
const selectedAgentId = ref<string | null>(null)
// 内置公共智能体(空状态选择卡片)
const builtinAgents = computed(() => agents.value.filter((a) => a.is_builtin))

// ===== 会话列表 =====
const conversations = ref<AgentConversation[]>([])
const currentConversationId = ref<string | null>(null)
const searchText = ref('')
// 侧栏开关(桌面默认展开, 移动端默认收起为抽屉)
const sidebarOpen = ref(typeof window !== 'undefined' && window.innerWidth >= 768)

// 当前会话信息(顶栏标题展示)
const currentConversation = computed(() =>
  conversations.value.find((c) => c.id === currentConversationId.value),
)

// ===== 聊天状态 =====
const messages = ref<ChatMessage[]>([])
const inputMessage = ref('')
const isSending = ref(false)
const streamingMessageId = ref<string | null>(null)
const messageListRef = ref<InstanceType<typeof ChatMessageList>>()

// 停止生成(中止 SSE)
let abortController: AbortController | null = null
let stopRequested = false

// 按日期分组会话(今天/昨天/7天内/更早), 支持标题搜索
const groupedConversations = computed(() => {
  const keyword = searchText.value.trim().toLowerCase()
  const filtered = conversations.value.filter(
    (c) => !keyword || (c.title || '新对话').toLowerCase().includes(keyword),
  )
  const groups: { label: string; items: AgentConversation[] }[] = [
    { label: '今天', items: [] },
    { label: '昨天', items: [] },
    { label: '7 天内', items: [] },
    { label: '更早', items: [] },
  ]
  const now = Date.now()
  const startToday = new Date().setHours(0, 0, 0, 0)
  const startYesterday = startToday - 86400000
  const start7d = startToday - 7 * 86400000
  for (const conv of filtered) {
    const t = new Date(conv.updated_at || conv.created_at).getTime() || now
    if (t >= startToday) groups[0].items.push(conv)
    else if (t >= startYesterday) groups[1].items.push(conv)
    else if (t >= start7d) groups[2].items.push(conv)
    else groups[3].items.push(conv)
  }
  return groups.filter((g) => g.items.length > 0)
})

// ===== 数据加载 =====
// 可用智能体列表(内置公共 + 本人创建)
const loadAgents = async () => {
  try {
    const res = await listAgents({ page: 1, size: 200 })
    agents.value = res.items
  } catch (error) {
    console.error('获取智能体列表失败:', error)
  }
}

// 会话列表(默认选中最近一个)
const loadConversations = async () => {
  try {
    const res = await listMyAgentConversations({ page: 1, size: 100 })
    conversations.value = res.items
    if (!currentConversationId.value && conversations.value.length > 0) {
      await selectConversation(conversations.value[0].id)
    }
  } catch (error) {
    console.error('获取对话列表失败:', error)
  }
}

/** 历史消息 blocks 归一化: 后端存 {node_name, stream_event_type, content}, 补齐 id/type */
const normalizeBlocks = (msg: ChatMessage): MessageBlock[] =>
  (msg.blocks ?? []).map((blk, i): MessageBlock => ({
    id: blk.id ?? `hist-${msg.id}-${i}`,
    node_name: blk.node_name ?? '',
    type: 'process',
    content: blk.content ?? '',
    stream_event_type: blk.stream_event_type,
  })).filter((blk) => blk.content)

// ===== 会话操作 =====
const handleCreateConversation = async () => {
  try {
    const id = await createAgentConversation({
      title: '新对话',
      agent_id: selectedAgentId.value,
    })
    await loadConversations()
    await selectConversation(id)
    ElMessage.success('对话已创建')
  } catch (error) {
    console.error('创建对话失败:', error)
    ElMessage.error('创建对话失败')
  }
}

// 选中会话并加载历史消息(同时收起侧栏; 恢复关联智能体与过程区块)
const selectConversation = async (conversationId: string) => {
  sidebarOpen.value = false
  currentConversationId.value = conversationId
  messages.value = []
  try {
    const conv = await getAgentConversation(conversationId)
    if (conv?.agent_id) {
      selectedAgentId.value = conv.agent_id
    }
    // 历史消息(倒序接口按时间正序展示, blocks 归一化供折叠区恢复)
    const res = await listAgentConversationMessages(conversationId, { page: 1, size: 200 })
    messages.value = [...res.items].reverse().map((msg) => ({
      ...msg,
      blocks: msg.role === 'assistant' ? normalizeBlocks(msg) : null,
    }))
    messageListRef.value?.scrollToBottom(true)
  } catch (error) {
    console.error('加载对话失败:', error)
  }
}

const handleDeleteConversation = async (conv: AgentConversation) => {
  try {
    await ElMessageBox.confirm(
      `确定删除对话"${conv.title || '新对话'}"吗？`,
      '删除对话',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    await deleteAgentConversation(conv.id)
    if (currentConversationId.value === conv.id) {
      currentConversationId.value = null
      messages.value = []
    }
    await loadConversations()
    ElMessage.success('删除成功')
  } catch (error) {
    console.log('取消删除或删除失败:', error)
  }
}

// ===== 流式事件分组 =====
// 按 (stream_event_type + node_name) 把过程内容累积到 blocks; answer 归入正文
let currentBlock: MessageBlock | null = null

const appendEvent = (msg: ChatMessage, event: {
  content?: string | null
  node_name?: string | null
  stream_event_type?: string | null
}) => {
  const content = event.content ?? ''
  if (!content) return
  const type = event.stream_event_type
  // 正式回答(或未分类事件) → 正文, 关闭当前过程块
  if (!type || type === StreamEventType.ANSWER) {
    msg.content += content
    currentBlock = null
    return
  }
  // 过程内容(思考/状态等) → 过程区块
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
// 发送消息(流式接收; 无会话时自动创建并携带所选智能体)
const handleSend = async () => {
  const message = inputMessage.value.trim()
  if (!message || isSending.value) return

  // 无会话时自动创建(标题取首条消息), 现代聊天交互: 直接输入即可开始
  if (!currentConversationId.value) {
    try {
      const id = await createAgentConversation({
        title: message.slice(0, 20),
        agent_id: selectedAgentId.value,
      })
      currentConversationId.value = id
      loadConversations()
    } catch (error) {
      console.error('创建对话失败:', error)
      ElMessage.error('创建对话失败')
      return
    }
  }

  // 追加用户消息
  messages.value.push({
    id: `local-${Date.now()}`,
    conversation_id: currentConversationId.value,
    role: 'user',
    content: message,
    created_at: new Date().toISOString(),
  })
  inputMessage.value = ''

  // 助手消息占位(流式填充正文与过程区块)
  const assistantMsg: ChatMessage = reactive({
    id: `local-${Date.now() + 1}`,
    conversation_id: currentConversationId.value,
    role: 'assistant',
    content: '',
    created_at: new Date().toISOString(),
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
    streamingMessageId.value = null
    isSending.value = false
    // 空回复兜底提示
    if (!assistantMsg.content && !(assistantMsg.blocks?.length)) {
      assistantMsg.content = stopRequested ? '（已停止生成）' : '（未收到回复，请重试）'
    }
    messageListRef.value?.scrollToBottom(true)
  }

  try {
    await sendAgentChatStream(
      currentConversationId.value,
      { message },
      // 错误回调(主动停止时不追加错误文案)
      (error: string) => {
        if (!stopRequested) assistantMsg.content += `\n\n> [错误] ${error}`
        finishStream()
      },
      // 完成回调(刷新会话列表)
      () => {
        finishStream()
        loadConversations()
      },
      // 拿到中止控制器(供"停止生成")
      (controller: AbortController) => {
        abortController = controller
      },
      // 完整事件回调: 按事件类型分组(正文/过程区块)
      (event) => appendEvent(assistantMsg, event),
    )
  } catch (error) {
    if (!stopRequested) assistantMsg.content += '\n\n> [发送失败，请重试]'
    finishStream()
  }
}

// 停止生成(中止 SSE 请求)
const handleStop = () => {
  stopRequested = true
  abortController?.abort()
}

onMounted(() => {
  loadAgents()
  loadConversations()
})
</script>

<style>
/* 抽屉遮罩过渡 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
