<template>
  <div flex flex-col h-app w-full bg-note-paper overflow-hidden>
    <div flex flex-1 min-h-0 w-full>
    <!-- 知识库问答: 可收起会话列表 + 居中消息流(过程区块/引用溯源) + 悬浮输入卡 -->
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
            <!-- 重命名 -->
            <button
              op-0 group-hover:op-100 shrink-0 p-1 rounded-md class="hover:bg-note-green/15" hover:text-note-green transition
              title="重命名对话" @click.stop="handleRenameConversation(conv)"
            >
              <el-icon :size="14"><EditPen /></el-icon>
            </button>
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

      <!-- 次级管理入口(小字低调, 不抢历史列表; 后续智能体管理等在此扩展) -->
      <div v-if="visibleManageLinks.length" px-3 py-2.5 border-t border-note space-y-0.5>
        <RouterLink
          v-for="link in visibleManageLinks" :key="link.index" :to="link.index"
          flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-note-sub
          hover:bg-note-tint hover:text-note-green transition-colors
        >
          <el-icon :size="13"><component :is="link.icon" /></el-icon>
          {{ link.label }}
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

      <!-- 消息流: 居中阅读宽度(过程区块 + 引用溯源 + 富文本) -->
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
            <h2 text-xl font-bold text-note>知识库问答</h2>
            <p mt-1 text-sm text-note-sub>选择关联知识库，回答将基于文档内容生成</p>
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

      <!-- 输入区: 悬浮卡片式输入框(知识库/思考模式与输入同行) -->
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
                v-model="selectedProjectIds" multiple collapse-tags collapse-tags-tooltip :max-collapse-tags="2"
                class="kb-select" size="small" placeholder="关联知识库" :disabled="isSending"
              >
                <el-option v-for="p in myProjects" :key="p.project_id" :label="p.project_name" :value="p.project_id" />
              </el-select>
              <!-- 深度思考开关(胶囊按钮) -->
              <el-tooltip content="启用后模型将进行更深入的推理分析" placement="top">
                <button
                  class="think-btn"
                  :class="{ active: deepThinking }"
                  @click="deepThinking = !deepThinking"
                >
                  <el-icon :size="13"><MagicStick /></el-icon>
                  深度思考
                </button>
              </el-tooltip>
            </template>
          </ChatComposer>
        </div>
      </div>
    </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  Plus, Search, Delete, Menu, MagicStick, ChatDotRound,
  EditPen, Document, List, DataAnalysis, Collection,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { usePermission } from '@/common/composables/usePermission'
import {
  createConversation,
  listMyConversations,
  getConversation,
  updateConversation,
  deleteConversation,
  listConversationMessages,
  sendRagChatStream,
} from '../api/conversation'
import { listMyProjects } from '../api/member'
import ChatMessageList from '@/common/components/chat/ChatMessageList.vue'
import ChatComposer from '@/common/components/chat/ChatComposer.vue'
import { StreamEventType } from '@/common/types/chat'
import type { MessageBlock } from '@/common/types/chat'
import type { Conversation, ChatMessage, MyProject } from '../types'

const { hasPerm } = usePermission()

// ===== 会话列表 =====
const conversations = ref<Conversation[]>([])
const currentConversationId = ref<string | null>(null)
const searchText = ref('')
// 侧栏开关(桌面默认展开, 移动端默认收起为抽屉)
const sidebarOpen = ref(typeof window !== 'undefined' && window.innerWidth >= 768)

// 当前会话信息(顶栏标题展示)
const currentConversation = computed(() =>
  conversations.value.find((c) => c.id === currentConversationId.value),
)

// 次级管理入口(低调收纳于侧栏底部, 后续管理页在此追加一项即可)
const visibleManageLinks = computed(() => [
  { label: '知识库管理', icon: markRaw(Collection), index: '/rag/project', perm: 'rag:project' },
  { label: '智能体管理', icon: markRaw(MagicStick), index: '/agent/manage', perm: 'agent:manage' },
].filter((l) => !l.perm || hasPerm(l.perm)))

// ===== 知识库关联 =====
const myProjects = ref<MyProject[]>([])
const selectedProjectIds = ref<string[]>([])

// ===== 聊天状态 =====
const messages = ref<ChatMessage[]>([])
const inputMessage = ref('')
const isSending = ref(false)
const deepThinking = ref(false)
const streamingMessageId = ref<string | null>(null)
const messageListRef = ref<InstanceType<typeof ChatMessageList>>()

// 停止生成(中止 SSE)
let abortController: AbortController | null = null
let stopRequested = false

// 空状态建议问题(点击即发送)
const suggestions = [
  { label: '提炼要点', question: '这份文档的核心观点是什么？', icon: markRaw(Document) },
  { label: '总结归纳', question: '帮我总结知识库中的关键信息', icon: markRaw(List) },
  { label: '撰写文稿', question: '根据知识库资料写一份会议纪要', icon: markRaw(EditPen) },
  { label: '对比分析', question: '对比文档中提到的几种方案优劣', icon: markRaw(DataAnalysis) },
]

// 按日期分组会话(今天/昨天/7天内/更早), 支持标题搜索
const groupedConversations = computed(() => {
  const keyword = searchText.value.trim().toLowerCase()
  const filtered = conversations.value.filter(
    (c) => !keyword || (c.title || '新对话').toLowerCase().includes(keyword),
  )
  const groups: { label: string; items: Conversation[] }[] = [
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
// 我可访问的知识库项目
const loadMyProjects = async () => {
  try {
    const res = await listMyProjects({ page: 1, size: 200 })
    myProjects.value = res.items
  } catch (error) {
    console.error('获取知识库列表失败:', error)
  }
}

// 会话列表(默认选中最近一个)
const loadConversations = async () => {
  try {
    const res = await listMyConversations({ page: 1, size: 100 })
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
    const id = await createConversation({
      title: '新对话',
      project_ids: selectedProjectIds.value,
    })
    await loadConversations()
    await selectConversation(id)
    ElMessage.success('对话已创建')
  } catch (error) {
    console.error('创建对话失败:', error)
    ElMessage.error('创建对话失败')
  }
}

// 选中会话并加载历史消息(同时收起侧栏; 恢复关联知识库与过程区块)
const selectConversation = async (conversationId: string) => {
  sidebarOpen.value = false
  currentConversationId.value = conversationId
  messages.value = []
  try {
    const conv = await getConversation(conversationId)
    if (conv?.project_ids?.length) {
      selectedProjectIds.value = conv.project_ids
    }
    // 历史消息(倒序接口按时间正序展示, blocks 归一化供折叠区恢复)
    const res = await listConversationMessages(conversationId, { page: 1, size: 200 })
    messages.value = [...res.items].reverse().map((msg) => ({
      ...msg,
      blocks: msg.role === 'assistant' ? normalizeBlocks(msg) : null,
    }))
    messageListRef.value?.scrollToBottom(true)
  } catch (error) {
    console.error('加载对话失败:', error)
  }
}

// 知识库选择变化时同步到当前会话(下次提问生效)
const handleProjectsChange = () => {
  // 仅作即时反馈, 实际关联在发送请求时携带
}

/** 重命名会话(弹窗输入新标题) */
const handleRenameConversation = async (conv: Conversation) => {
  try {
    const { value } = await ElMessageBox.prompt('请输入新的对话标题', '重命名对话', {
      confirmButtonText: '保存',
      cancelButtonText: '取消',
      inputValue: conv.title || '',
      inputPattern: /\S+/,
      inputErrorMessage: '标题不能为空',
    })
    await updateConversation(conv.id, { title: value.trim() })
    conv.title = value.trim()
    ElMessage.success('已重命名')
  } catch {
    // 用户取消
  }
}

const handleDeleteConversation = async (conv: Conversation) => {
  try {
    await ElMessageBox.confirm(
      `确定删除对话"${conv.title || '新对话'}"吗？`,
      '删除对话',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    await deleteConversation(conv.id)
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

// 点击建议问题直接发送
const applySuggestion = (question: string) => {
  inputMessage.value = question
  handleSend()
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
  // 过程内容(思考/检索/文件生成等) → 过程区块
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
// 发送消息(流式接收; 无会话时自动创建)
const handleSend = async () => {
  const message = inputMessage.value.trim()
  if (!message || isSending.value) return

  // 无会话时自动创建(标题取首条消息), 现代聊天交互: 直接输入即可开始
  if (!currentConversationId.value) {
    try {
      const id = await createConversation({
        title: message.slice(0, 20),
        project_ids: selectedProjectIds.value,
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
    await sendRagChatStream(
      currentConversationId.value,
      {
        message,
        project_ids: selectedProjectIds.value,
        deep_thinking: deepThinking.value,
      },
      // 流式内容回调(仅正文, 兼容旧签名)
      () => {},
      // 错误回调(主动停止时不追加错误文案)
      (error: string) => {
        if (!stopRequested) assistantMsg.content += `\n\n> [错误] ${error}`
        finishStream()
      },
      // 完成回调(刷新会话列表, 标题可能被自动总结更新)
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
  loadMyProjects()
  loadConversations()
})
</script>

<style scoped>
/* 深度思考胶囊按钮(与输入卡内知识库选择器统一风格) */
.think-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-radius: 9999px;
  border: 1px solid transparent;
  background: var(--note-tint, #e7f3e9);
  color: var(--note-sub, #6b7f6e);
  font-size: 12px;
  white-space: nowrap;
  cursor: pointer;
  transition: all 0.2s;
}

.think-btn:hover {
  color: var(--note, #2f5d43);
}

.think-btn.active {
  background: var(--el-bg-color, #fff);
  border-color: var(--note-green, #6cbf8f);
  color: var(--note-green, #6cbf8f);
}
</style>

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
