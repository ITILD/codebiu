<template>
  <div flex h-app w-full bg-note-paper overflow-hidden>
    <!-- 知识库问答: Trae 风格现代 AI 对话(左侧会话列表 + 居中消息流 + 悬浮输入卡)
         注意: 注释不可置于模板顶层(会变成多根组件, 破坏路由 Transition) -->
    <!-- 移动端抽屉遮罩 -->
    <Transition name="fade">
      <div v-if="drawerOpen" fixed inset-0 z-20 class="bg-black/30" md:hidden @click="drawerOpen = false" />
    </Transition>

    <!-- 会话列表(桌面常驻, 移动端侧滑抽屉) -->
    <aside
      fixed md:static inset-y-0 left-0 z-30 w-72 shrink-0 flex flex-col bg-note-soft border-r border-note
      transition-transform duration-300 md:translate-x-0
      :class="drawerOpen ? 'translate-x-0' : '-translate-x-full'"
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
            <button
              op-0 group-hover:op-100 shrink-0 p-1 rounded-md class="hover:bg-red-4/15" hover:text-red-5 transition
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
    </aside>

    <!-- 右侧聊天区域 -->
    <section flex-1 flex flex-col min-w-0 relative>
      <!-- 顶部栏: 汉堡(移动端) + 知识库选择 + 深度思考 -->
      <header
        flex items-center gap-2 px-3 md:px-5 py-2.5 border-b border-note
        class="bg-note-soft/70" backdrop-blur
      >
        <button
          md:hidden rounded-full p-2 text-note hover:bg-note-tint transition
          title="会话列表" @click="drawerOpen = true"
        >
          <el-icon :size="20"><Menu /></el-icon>
        </button>

        <div flex-1 min-w-0>
          <el-select
            v-model="selectedProjectIds" multiple collapse-tags collapse-tags-tooltip :max-collapse-tags="2"
            w-full sm:w-80 placeholder="关联知识库（可多选）" :disabled="isSending"
            @change="handleProjectsChange"
          >
            <el-option v-for="p in myProjects" :key="p.project_id" :label="p.project_name" :value="p.project_id" />
          </el-select>
        </div>

        <!-- 深度思考开关(胶囊按钮) -->
        <el-tooltip content="启用后模型将进行更深入的推理分析" placement="bottom">
          <button
            flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs whitespace-nowrap transition-all
            :class="deepThinking
              ? 'bg-note-tint border-note-green text-note-green'
              : 'border-note text-note-sub hover:text-note'"
            @click="deepThinking = !deepThinking"
          >
            <el-icon :size="14"><MagicStick /></el-icon>
            深度思考
          </button>
        </el-tooltip>
      </header>

      <!-- 消息流(居中阅读宽度) -->
      <div ref="chatContainer" flex-1 overflow-y-auto overscroll-contain>
        <div max-w-3xl mx-auto w-full px-4 py-6 flex flex-col gap-6>
          <!-- 空状态: 问候 + 建议问题卡片 -->
          <div v-if="messages.length === 0" class="min-h-[60%]" flex flex-col items-center justify-center py-8 text-center>
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

          <!-- 消息列表 -->
          <template v-for="msg in messages" :key="msg.id">
            <!-- 用户消息: 右侧淡绿气泡 -->
            <div v-if="msg.role === 'user'" flex justify-end>
              <div
                class="max-w-[85%]" px-4 py-2.5 rounded-2xl rounded-br-md bg-note-tint text-note
                text-sm leading-relaxed whitespace-pre-wrap break-words
              >
                {{ msg.content }}
              </div>
            </div>

            <!-- 助手消息: 头像 + Markdown 全宽 -->
            <div v-else flex gap-3 group>
              <div w-8 h-8 rounded-full bg-note-green text-white flex-center shrink-0 mt-0.5 shadow-note>
                <el-icon :size="16"><MagicStick /></el-icon>
              </div>
              <div flex-1 min-w-0>
                <!-- 等待首个 token: 思考动画 -->
                <div v-if="!msg.content" flex items-center gap-1 py-2>
                  <span class="thinking-dot" />
                  <span class="thinking-dot" />
                  <span class="thinking-dot" />
                </div>
                <!-- Markdown 正文(流式生成中显示光标) -->
                <div
                  v-else
                  class="rag-md"
                  :class="{ 'is-streaming': msg.id === streamingMessageId }"
                  v-html="renderMarkdown(msg.content)"
                />
                <!-- 消息操作: 复制 -->
                <div v-if="msg.content && msg.id !== streamingMessageId" flex gap-1 mt-2 opacity-0 group-hover:opacity-100 transition-opacity>
                  <button
                    flex items-center gap-1 px-2 py-1 rounded-md text-xs text-note-sub hover:bg-note-tint hover:text-note-green transition
                    @click="handleCopy(msg.content)"
                  >
                    <el-icon :size="13"><CopyDocument /></el-icon>
                    复制
                  </button>
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>

      <!-- 输入区: 悬浮卡片式输入框 -->
      <div px-3 md:px-4 pb-3 md:pb-4>
        <div max-w-3xl mx-auto class="chat-input-card">
          <el-input
            v-model="inputMessage"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 8 }"
            placeholder="输入你的问题..."
            @keydown.enter.exact.prevent="handleSend"
            @keydown.enter.shift.prevent
          />
          <div flex items-center justify-between px-2.5 pb-2.5>
            <span hidden sm:block text-xs text-note-sub>Enter 发送 · Shift+Enter 换行</span>
            <span sm:hidden />
            <!-- 停止生成 / 发送 -->
            <el-tooltip v-if="isSending" content="停止生成" placement="top">
              <button
                w-9 h-9 rounded-full bg-note-card border border-note text-note flex-center
                hover:border-red-4 hover:text-red-5 transition
                @click="handleStop"
              >
                <el-icon :size="16"><VideoPause /></el-icon>
              </button>
            </el-tooltip>
            <el-tooltip v-else content="发送" placement="top">
              <button
                w-9 h-9 rounded-full flex-center transition-all
                :class="canSend
                  ? 'bg-note-green text-white shadow-note hover:opacity-90 active:scale-95'
                  : 'bg-note-tint text-note-sub cursor-not-allowed'"
                :disabled="!canSend"
                @click="handleSend"
              >
                <el-icon :size="16"><Promotion /></el-icon>
              </button>
            </el-tooltip>
          </div>
        </div>
        <p text-center text-xs text-note-sub mt-2>内容由 AI 基于知识库生成，请注意甄别</p>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import {
  Plus, Search, Delete, Menu, MagicStick, ChatDotRound,
  CopyDocument, Promotion, VideoPause, Document, List, EditPen, DataAnalysis,
} from '@element-plus/icons-vue'
import { marked } from 'marked'
import {
  createConversation,
  listMyConversations,
  getConversation,
  deleteConversation,
  listConversationMessages,
  sendRagChatStream,
} from '@/api/rag/conversation'
import { listMyProjects } from '@/api/rag/member'
import type { Conversation, ChatMessage, MyProject } from '@/types/rag'
import { ElMessage, ElMessageBox } from 'element-plus'

// Markdown 渲染(GFM + 换行即断行, 贴近聊天场景)
marked.setOptions({ gfm: true, breaks: true })
const renderMarkdown = (content: string) => marked.parse(content) as string

// ===== 会话列表 =====
const conversations = ref<Conversation[]>([])
const currentConversationId = ref<string | null>(null)
const searchText = ref('')
const drawerOpen = ref(false)

// ===== 知识库关联 =====
const myProjects = ref<MyProject[]>([])
const selectedProjectIds = ref<string[]>([])

// ===== 聊天状态 =====
const messages = ref<ChatMessage[]>([])
const inputMessage = ref('')
const isSending = ref(false)
const deepThinking = ref(false)
const streamingMessageId = ref<string | null>(null)
const chatContainer = ref<HTMLElement>()

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

// 是否可发送(无会话时自动创建, 故只看内容)
const canSend = computed(() => !!inputMessage.value.trim() && !isSending.value)

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

// ===== 智能滚动: 仅当用户接近底部时才跟随(阅读历史时不打扰) =====
const isNearBottom = () => {
  const el = chatContainer.value
  if (!el) return true
  return el.scrollHeight - el.scrollTop - el.clientHeight < 120
}
const scrollToBottom = (force = false) => {
  nextTick(() => {
    if (!chatContainer.value) return
    if (force || isNearBottom()) chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  })
}

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

// 选中会话并加载历史消息(移动端同时收起抽屉)
const selectConversation = async (conversationId: string) => {
  drawerOpen.value = false
  currentConversationId.value = conversationId
  messages.value = []
  try {
    // 会话详情(恢复关联知识库选择)
    const conv = await getConversation(conversationId)
    if (conv?.project_ids?.length) {
      selectedProjectIds.value = conv.project_ids
    }
    // 历史消息(倒序接口按时间正序展示)
    const res = await listConversationMessages(conversationId, { page: 1, size: 200 })
    messages.value = [...res.items].reverse()
    scrollToBottom(true)
  } catch (error) {
    console.error('加载对话失败:', error)
  }
}

// 知识库选择变化时同步到当前会话(下次提问生效)
const handleProjectsChange = () => {
  // 仅作即时反馈, 实际关联在发送请求时携带
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

// 复制消息内容
const handleCopy = async (text: string) => {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败')
  }
}

// 点击建议问题直接发送
const applySuggestion = (question: string) => {
  inputMessage.value = question
  handleSend()
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
  scrollToBottom(true)

  // 助手消息占位(流式填充)
  const assistantMsg: ChatMessage = {
    id: `local-${Date.now() + 1}`,
    conversation_id: currentConversationId.value,
    role: 'assistant',
    content: '',
    created_at: new Date().toISOString(),
  }
  messages.value.push(assistantMsg)
  streamingMessageId.value = assistantMsg.id
  isSending.value = true
  stopRequested = false
  abortController = null

  // 结束收尾(幂等)
  function finishStream() {
    streamingMessageId.value = null
    isSending.value = false
    scrollToBottom(true)
  }

  try {
    await sendRagChatStream(
      currentConversationId.value,
      {
        message,
        project_ids: selectedProjectIds.value,
        deep_thinking: deepThinking.value,
      },
      // 流式内容回调
      (content: string) => {
        assistantMsg.content += content
        scrollToBottom()
      },
      // 错误回调(主动停止时不追加错误文案)
      (error: string) => {
        if (!stopRequested) assistantMsg.content += `\n\n> [错误] ${error}`
        finishStream()
      },
      // 完成回调
      () => {
        finishStream()
        // 刷新会话列表(标题可能被自动总结更新)
        loadConversations()
      },
      // 拿到中止控制器(供"停止生成")
      (controller: AbortController) => {
        abortController = controller
      },
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

<style>
/* ===== 输入卡片(悬浮纸片, 聚焦苔绿描边) ===== */
.chat-input-card {
  border-radius: 1rem;
  background: var(--el-bg-color);
  border: 1px solid var(--note-border);
  box-shadow: 0 2px 12px rgba(108, 191, 143, 0.14);
  transition: border-color 0.2s;
}

.chat-input-card:focus-within {
  border-color: var(--note-green);
}

/* el-input textarea 无边框融入卡片 */
.chat-input-card .el-textarea__inner {
  box-shadow: none !important;
  background: transparent;
  padding: 12px 14px 4px;
  font-size: 0.9rem;
  line-height: 1.6;
}

/* ===== Markdown 正文(助手消息) ===== */
.rag-md {
  font-size: 0.9rem;
  line-height: 1.75;
  color: var(--el-text-color-primary);
  word-break: break-word;
}

.rag-md > :first-child {
  margin-top: 0;
}

.rag-md > :last-child {
  margin-bottom: 0;
}

.rag-md p {
  margin: 0.5em 0;
}

.rag-md h1,
.rag-md h2,
.rag-md h3,
.rag-md h4 {
  margin: 1em 0 0.4em;
  font-weight: 600;
}

.rag-md h1 {
  font-size: 1.25rem;
}

.rag-md h2 {
  font-size: 1.15rem;
}

.rag-md h3 {
  font-size: 1.05rem;
}

.rag-md ul,
.rag-md ol {
  padding-left: 1.25em;
  margin: 0.5em 0;
}

.rag-md li {
  margin: 0.25em 0;
}

.rag-md li > p {
  margin: 0;
}

.rag-md a {
  color: var(--note-green);
  text-decoration: none;
  border-bottom: 1px dashed var(--note-green);
}

.rag-md blockquote {
  margin: 0.6em 0;
  padding: 0.2em 0 0.2em 0.9em;
  border-left: 3px solid var(--note-green);
  border-radius: 2px;
  color: var(--el-text-color-secondary);
}

/* 行内代码: 苔绿胶囊 */
.rag-md code {
  background: var(--el-fill-color-light);
  border-radius: 4px;
  padding: 0.15em 0.4em;
  font-size: 0.85em;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  color: var(--note-green-deep);
}

html.dark .rag-md code {
  color: var(--note-green);
  background: rgba(136, 210, 167, 0.12);
}

/* 代码块: 深绿纸面 */
.rag-md pre {
  background: var(--note-soft);
  border: 1px solid var(--note-border);
  border-radius: 10px;
  padding: 0.9em 1em;
  overflow-x: auto;
  margin: 0.7em 0;
}

html.dark .rag-md pre {
  background: #101c15;
}

.rag-md pre code {
  background: none;
  padding: 0;
  color: var(--el-text-color-primary);
  font-size: 0.85em;
  line-height: 1.6;
}

/* 表格 */
.rag-md table {
  border-collapse: collapse;
  margin: 0.7em 0;
  font-size: 0.85em;
  display: block;
  overflow-x: auto;
  max-width: 100%;
}

.rag-md th,
.rag-md td {
  border: 1px solid var(--note-border);
  padding: 6px 12px;
}

.rag-md th {
  background: var(--el-fill-color-light);
  font-weight: 600;
}

.rag-md hr {
  border: none;
  border-top: 1px solid var(--note-border);
  margin: 1em 0;
}

.rag-md img {
  max-width: 100%;
  border-radius: 8px;
}

/* 流式生成中的光标 */
.rag-md.is-streaming::after {
  content: '';
  display: inline-block;
  width: 7px;
  height: 15px;
  margin-left: 2px;
  vertical-align: text-bottom;
  background: var(--note-green);
  animation: rag-blink 1s step-end infinite;
}

@keyframes rag-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* 等待首个 token 的思考动画(三点弹跳) */
.thinking-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--note-green);
  display: inline-block;
  animation: rag-bounce 1.2s ease-in-out infinite;
}

.thinking-dot:nth-child(2) {
  animation-delay: 0.15s;
}

.thinking-dot:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes rag-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-4px); opacity: 1; }
}

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
