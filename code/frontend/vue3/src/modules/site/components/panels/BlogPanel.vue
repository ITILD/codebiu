<template>
  <div class="w-full">
    <!-- 搜索栏: 标题/状态/来源过滤 + 新建入口 -->
    <TableSearchBar
      v-model="queryParams"
      :fields="searchFields"
      @search="handleSearch"
      @reset="handleSearch"
    >
      <template #actions>
        <el-button type="primary" :icon="EditPen" @click="openCreate">写文章</el-button>
      </template>
    </TableSearchBar>

    <!-- 首轮加载: 表格骨架(搜索/刷新仍用表格自身 loading 遮罩) -->
    <NoteSkeleton
      v-if="loading && tableData.length === 0"
      variant="table"
      :rows="8"
      class="rounded-xl border border-note bg-note-card shadow-note px-2 py-3"
    />
    <!-- 文章表格 -->
    <el-table v-else :data="tableData" v-loading="loading" stripe w-full>
      <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">
          <el-link type="primary" @click="goRead(row)">{{ row.title }}</el-link>
        </template>
      </el-table-column>
      <el-table-column label="来源" min-width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.source_type === 'url' ? 'warning' : 'primary'" size="small" effect="plain">
            {{ row.source_type === 'url' ? '外链' : 'markdown' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="category" label="分类" min-width="90" show-overflow-tooltip>
        <template #default="{ row }">{{ row.category || '—' }}</template>
      </el-table-column>
      <el-table-column label="状态" min-width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="row.status === 'published' ? 'success' : 'info'" size="small">
            {{ row.status === 'published' ? '已发布' : '草稿' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" min-width="160">
        <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" min-width="210" :fixed="isMd ? 'right' : false">
        <template #default="{ row }">
          <el-button size="small" plain @click="openEdit(row)">编辑</el-button>
          <el-button
            size="small"
            :type="row.status === 'published' ? 'info' : 'success'"
            plain
            @click="togglePublish(row)"
          >{{ row.status === 'published' ? '下架' : '发布' }}</el-button>
          <el-button size="small" type="danger" plain @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页(手机居中, 桌面靠右) -->
    <div class="mt-4 flex flex-wrap justify-center sm:justify-end">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.size"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="fetchData"
      />
    </div>

    <!-- 编辑/创建对话框: markdown 在线编辑(左写右预览) 或 关联 URL, 支持全屏编辑 -->
    <el-dialog
      v-model="dialogVisible"
      :title="currentId ? '编辑文章' : '写文章'"
      width="90%"
      :class="editorFullscreen ? '' : 'max-w-[960px]!'"
      :fullscreen="editorFullscreen"
      :close-on-click-modal="false"
    >
      <el-form :model="form" label-width="70px">
        <!-- 来源切换 -->
        <el-form-item label="来源">
          <el-radio-group v-model="form.source_type" @change="onSourceChange">
            <el-radio-button value="markdown">在线编辑</el-radio-button>
            <el-radio-button value="url">关联 URL</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="标题" required>
          <el-input v-model="form.title" placeholder="请输入文章标题" maxlength="200" />
        </el-form-item>
        <el-form-item v-if="form.source_type === 'url'" label="链接" required>
          <el-input v-model="form.url" placeholder="https://example.com/post/1">
            <template #prepend><i class="i-ep-link" /></template>
          </el-input>
        </el-form-item>

        <!-- markdown 编辑: 工具栏 + 桌面双栏同步预览 / 移动端 tab 切换 -->
        <el-form-item v-if="form.source_type === 'markdown'" label="正文">
          <div class="w-full overflow-hidden rounded-lg border border-note bg-note-paper">
            <!-- 工具栏: 快捷插入 + 字数 + 全屏 -->
            <div
              class="flex flex-wrap items-center gap-0.5 border-b border-note bg-note-soft/60 px-1.5 py-1"
            >
              <button
                v-for="act in toolbarActions"
                :key="act.label"
                type="button"
                class="flex h-7 min-w-7 items-center justify-center rounded px-1.5 text-xs text-note-sub transition-colors hover:bg-note-glass hover:text-note"
                :title="act.label"
                @click="act.run()"
              >
                <span class="inline-flex items-center leading-none" v-html="act.html" />
              </button>
              <span class="ml-auto pl-2 text-[11px] text-note-sub">{{ form.content.length }} 字</span>
              <el-divider direction="vertical" />
              <button
                type="button"
                class="flex h-7 min-w-7 items-center justify-center rounded px-1.5 text-note-sub transition-colors hover:bg-note-glass hover:text-note"
                :title="editorFullscreen ? '退出全屏' : '全屏编辑'"
                @click="editorFullscreen = !editorFullscreen"
              >
                <i :class="editorFullscreen ? 'i-ep-close' : 'i-ep-full-screen'" />
              </button>
            </div>

            <!-- 桌面: 双栏(编辑 | 预览), 滚动同步(scroll 不冒泡, 用 capture 捕获 textarea 滚动) -->
            <div v-if="!isMd" class="grid grid-cols-2" :style="{ height: editorHeight }">
              <div class="h-full min-w-0 border-r border-note" @scroll.capture="syncPreviewScroll">
                <el-input
                  ref="editorInputRef"
                  v-model="form.content"
                  type="textarea"
                  placeholder="支持 markdown 语法，可插入 mermaid 图表..."
                  class="editor-input"
                />
              </div>
              <div ref="previewEl" class="h-full min-w-0 overflow-y-auto px-4 py-3">
                <MarkdownView :content="form.content" />
              </div>
            </div>

            <!-- 移动端: 编辑/预览 tab -->
            <el-tabs v-else v-model="editorTab" class="editor-tabs px-2">
              <el-tab-pane label="编辑" name="edit">
                <el-input
                  ref="editorInputRef"
                  v-model="form.content"
                  type="textarea"
                  :rows="12"
                  placeholder="支持 markdown 语法，可插入 mermaid 图表..."
                  class="font-mono"
                />
              </el-tab-pane>
              <el-tab-pane label="预览" name="preview">
                <div class="max-h-[420px] overflow-y-auto rounded-lg bg-note-paper p-3">
                  <MarkdownView :content="form.content" />
                </div>
              </el-tab-pane>
            </el-tabs>
          </div>
        </el-form-item>

        <el-form-item label="分类">
          <el-input v-model="form.category" placeholder="如: 技术 / 生活 / 转载(可选)" maxlength="50" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch
            v-model="publishNow"
            active-text="发布"
            inactive-text="草稿"
            :active-value="true"
            :inactive-value="false"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { EditPen } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createBlogPost,
  deleteBlogPost,
  listMyPosts,
  updateBlogPost,
} from '../../api/blog'
import type { BlogPost, BlogPostCreate, PostSource } from '../../types/blog'
import MarkdownView from '../MarkdownView.vue'
import type { SearchField } from '@/common/components/TableSearchBar.vue'
import { useResponsive } from '@/common/composables/useResponsive'

// 响应式断点(md 以下走移动端布局)
const { isMd } = useResponsive()

// 搜索字段(标题/状态/来源)
const searchFields: SearchField[] = [
  { prop: 'title', label: '标题' },
  {
    prop: 'status', label: '状态', type: 'select', options: [
      { label: '草稿', value: 'draft' },
      { label: '已发布', value: 'published' },
    ],
  },
  {
    prop: 'source_type', label: '来源', type: 'select', options: [
      { label: '在线编辑', value: 'markdown' },
      { label: '外链', value: 'url' },
    ],
  },
]

const queryParams = ref<Record<string, unknown>>({ title: '', status: undefined, source_type: undefined })

const pagination = ref({ page: 1, size: 10 })

const tableData = ref<BlogPost[]>([])
const total = ref(0)
const loading = ref(false)

// 获取文章列表(携带过滤参数)
async function fetchData() {
  loading.value = true
  try {
    const { title, status, source_type } = queryParams.value
    const resp = await listMyPosts({
      ...pagination.value,
      title: (title as string) || undefined,
      status: (status as string) || undefined,
      source_type: (source_type as string) || undefined,
    })
    tableData.value = resp.items
    total.value = resp.total
  } catch (error) {
    console.error('获取文章列表失败:', error)
    ElMessage.error('获取文章列表失败，请重试')
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pagination.value.page = 1
  fetchData()
}

// 编辑对话框状态
const dialogVisible = ref(false)
const currentId = ref<string | null>(null)
const submitting = ref(false)
const editorTab = ref<'edit' | 'preview'>('edit')
const publishNow = ref(false)
/** 全屏编辑 */
const editorFullscreen = ref(false)

const form = reactive({
  title: '',
  source_type: 'markdown' as PostSource,
  content: '',
  url: '',
  category: '',
})

// ---------- markdown 编辑器: 工具栏 + 光标操作 + 同步滚动 ----------
const editorInputRef = ref<{ $el?: HTMLElement } | null>(null)
const previewEl = ref<HTMLElement | null>(null)

/** 获取原生 textarea 元素 */
function taEl(): HTMLTextAreaElement | null {
  return editorInputRef.value?.$el?.querySelector('textarea') ?? null
}

/** 包裹选中文本(无选中时插入占位符并选中, 便于直接覆盖输入) */
function wrapSelection(before: string, after: string, placeholder: string) {
  const ta = taEl()
  if (!ta) return
  const s = ta.selectionStart
  const e = ta.selectionEnd
  const selected = form.content.slice(s, e) || placeholder
  form.content = form.content.slice(0, s) + before + selected + after + form.content.slice(e)
  nextTick(() => {
    ta.focus()
    ta.setSelectionRange(s + before.length, s + before.length + selected.length)
  })
}

/** 在光标处插入块级片段(前后保证换行) */
function insertBlock(snippet: string) {
  const ta = taEl()
  if (!ta) return
  const s = ta.selectionStart
  const e = ta.selectionEnd
  const head = form.content.slice(0, s)
  const tail = form.content.slice(e)
  // 光标前补空行, 保证块级语法独立成段
  const pad = !head ? '' : head.endsWith('\n\n') ? '' : head.endsWith('\n') ? '\n' : '\n\n'
  const body = head + pad + snippet
  form.content = body + '\n' + tail
  nextTick(() => {
    ta.focus()
    const pos = body.length + 1
    ta.setSelectionRange(pos, pos)
  })
}

/** 当前行首插入前缀(标题/引用/列表), 已有前缀则跳过 */
function prefixLine(prefix: string) {
  const ta = taEl()
  if (!ta) return
  const s = ta.selectionStart
  const lineStart = form.content.lastIndexOf('\n', s - 1) + 1
  if (form.content.slice(lineStart).startsWith(prefix)) {
    ElMessage.info({ message: `该行已有「${prefix.trim()}」前缀`, grouping: true })
    return
  }
  form.content = form.content.slice(0, lineStart) + prefix + form.content.slice(lineStart)
  nextTick(() => {
    ta.focus()
    const pos = s + prefix.length
    ta.setSelectionRange(pos, pos)
  })
}

/** 工具栏动作(文本符号/图标 + 插入逻辑) */
const toolbarActions = [
  { label: '一级标题', html: '<b>H1</b>', run: () => prefixLine('# ') },
  { label: '二级标题', html: '<b>H2</b>', run: () => prefixLine('## ') },
  { label: '三级标题', html: '<b>H3</b>', run: () => prefixLine('### ') },
  { label: '加粗', html: '<b>B</b>', run: () => wrapSelection('**', '**', '加粗文本') },
  { label: '斜体', html: '<i>I</i>', run: () => wrapSelection('*', '*', '斜体文本') },
  { label: '删除线', html: '<s>S</s>', run: () => wrapSelection('~~', '~~', '删除文本') },
  { label: '引用', html: '❝', run: () => prefixLine('> ') },
  {
    label: '行内代码',
    html: '<span style="font-family:ui-monospace,monospace">&lt;/&gt;</span>',
    run: () => wrapSelection('`', '`', '代码'),
  },
  {
    label: '代码块',
    html: '<span style="font-family:ui-monospace,monospace;font-size:10px">```</span>',
    run: () => insertBlock('```\n代码\n```'),
  },
  { label: '链接', html: '<i class="i-ep-link"></i>', run: () => wrapSelection('[', '](https://)', '链接文字') },
  {
    label: '表格',
    html: '<i class="i-ep-grid"></i>',
    run: () => insertBlock('| 列一 | 列二 | 列三 |\n| --- | --- | --- |\n| 内容 | 内容 | 内容 |'),
  },
  {
    label: 'mermaid 图表',
    html: '<i class="i-ep-connection"></i>',
    run: () => insertBlock('```mermaid\ngraph TD\n  A --> B\n```'),
  },
  { label: '分割线', html: '—', run: () => insertBlock('---') },
]

/** 编辑区高度(全屏时撑满可视区) */
const editorHeight = computed(() =>
  editorFullscreen.value ? 'calc(100vh - 360px)' : '460px',
)

/** 编辑 → 预览 滚动同步(按滚动比例) */
function syncPreviewScroll(event: Event) {
  const ta = event.target as HTMLTextAreaElement
  const preview = previewEl.value
  if (!preview || ta.scrollHeight <= ta.clientHeight) return
  const ratio = ta.scrollTop / (ta.scrollHeight - ta.clientHeight)
  preview.scrollTop = ratio * (preview.scrollHeight - preview.clientHeight)
}

/** 切换来源时清空另一来源的内容, 避免脏数据 */
function onSourceChange() {
  if (form.source_type === 'url') form.content = ''
  else form.url = ''
}

function resetForm() {
  currentId.value = null
  form.title = ''
  form.source_type = 'markdown'
  form.content = ''
  form.url = ''
  form.category = ''
  publishNow.value = false
  editorTab.value = 'edit'
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: BlogPost) {
  resetForm()
  currentId.value = row.id
  form.title = row.title
  form.source_type = row.source_type
  form.content = row.content ?? ''
  form.url = row.url ?? ''
  form.category = row.category ?? ''
  publishNow.value = row.status === 'published'
  dialogVisible.value = true
}

// 保存(创建或更新)
async function handleSubmit() {
  if (!form.title.trim()) {
    ElMessage.warning('请输入文章标题')
    return
  }
  if (form.source_type === 'url' && !form.url.trim()) {
    ElMessage.warning('请输入关联的 URL')
    return
  }
  submitting.value = true
  try {
    const payload: BlogPostCreate = {
      title: form.title.trim(),
      source_type: form.source_type,
      category: form.category.trim() || null,
      status: publishNow.value ? 'published' : 'draft',
    }
    if (form.source_type === 'url') payload.url = form.url.trim()
    else payload.content = form.content

    if (currentId.value) {
      await updateBlogPost(currentId.value, payload)
      ElMessage.success('文章已更新')
    } else {
      await createBlogPost(payload)
      ElMessage.success(publishNow.value ? '文章已发布' : '草稿已保存')
    }
    dialogVisible.value = false
    fetchData()
  } catch (error) {
    console.error('保存文章失败:', error)
    ElMessage.error('保存失败，请重试')
  } finally {
    submitting.value = false
  }
}

// 发布/下架切换
async function togglePublish(row: BlogPost) {
  const next = row.status === 'published' ? 'draft' : 'published'
  try {
    await updateBlogPost(row.id, { status: next })
    ElMessage.success(next === 'published' ? '已发布' : '已下架为草稿')
    fetchData()
  } catch (error) {
    console.error('状态切换失败:', error)
    ElMessage.error('操作失败，请重试')
  }
}

// 删除
async function handleDelete(row: BlogPost) {
  try {
    await ElMessageBox.confirm(`确定删除文章「${row.title}」吗？此操作不可恢复。`, '警告', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消',
    })
    await deleteBlogPost(row.id)
    ElMessage.success('删除成功')
    if (tableData.value.length === 1 && pagination.value.page > 1) pagination.value.page -= 1
    fetchData()
  } catch {
    // 用户取消
  }
}

const router = useRouter()

/** 跳转到展示页阅读 */
function goRead(row: BlogPost) {
  router.push({ path: '/site/blog_view', query: { id: row.id } })
}

const formatDateTime = (v: string) => new Date(v).toLocaleString('zh-CN')

onMounted(fetchData)
</script>

<style scoped>
/* 编辑器 textarea 填满左栏(无边框融入卡片容器) */
.editor-input {
  height: 100%;
}
.editor-input :deep(.el-textarea__inner) {
  height: 100%;
  resize: none;
  border: none;
  border-radius: 0;
  box-shadow: none;
  background: transparent;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 13px;
  line-height: 1.7;
}
</style>
