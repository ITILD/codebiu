<template>
  <div p-2 w-full flex flex-col h-app>
    <!-- 页头: 返回 + 面包屑(项目名=项目根文件夹) + 搜索 + 新建文件夹 + 上传 -->
    <div mb-3 flex flex-wrap items-center gap-2>
      <el-button :icon="Back" @click="router.push('/rag/project')" />
      <el-breadcrumb separator="/" flex-1 min-w-0>
        <el-breadcrumb-item>
          <span cursor-pointer hover:text-note-green @click="handleGoto(-1)">{{ projectName }}</span>
        </el-breadcrumb-item>
        <el-breadcrumb-item v-for="(crumb, idx) in breadcrumbs" :key="crumb.id">
          <span cursor-pointer hover:text-note-green @click="handleGoto(idx)">{{ crumb.name }}</span>
        </el-breadcrumb-item>
      </el-breadcrumb>
      <el-input
        class="w-full sm:w-56"
        v-model="searchQuery"
        placeholder="按名称搜索"
        clearable
        :prefix-icon="Search"
        @input="handleSearchDebounced"
        @clear="handleSearchDebounced"
      />
      <el-button :icon="FolderAdd" @click="handleCreateFolder" :disabled="loading">新建文件夹</el-button>
      <el-upload :show-file-list="false" :before-upload="handleUpload" :disabled="uploading"
        accept=".txt,.md,.pdf,.docx,.xlsx,.pptx,.csv,.html,.json">
        <el-button type="primary" :loading="uploading" :icon="Upload">
          {{ uploading ? '上传中' : '上传文档' }}
        </el-button>
      </el-upload>
    </div>

    <!-- 条目表格(目录+文件混合, 目录排前; 文件行携带文档级联查字段) -->
    <el-table v-loading="loading" :data="entries" stripe w-full flex-1 @row-dblclick="handleOpen">
      <el-table-column label="名称" min-width="240" show-overflow-tooltip>
        <template #default="{ row }">
          <div flex items-center gap-2 cursor-pointer @click="handleOpen(row)">
            <el-icon text-lg :class="row.is_directory ? 'text-amber-500' : fileIconClass(row.file_extension)">
              <Folder v-if="row.is_directory" />
              <Document v-else />
            </el-icon>
            <span>{{ row.name }}</span>
            <el-tag v-if="row.is_directory" size="small" type="warning" effect="plain">目录</el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="类型" min-width="90" align="center">
        <template #default="{ row }">
          <el-tag v-if="!row.is_directory" size="small" type="info">
            {{ (row.file_extension || '').toUpperCase() }}
          </el-tag>
        </template>
      </el-table-column>
      <!-- 解析状态(仅文件行): 失败悬浮原因; 解析中/待解析展示入库步骤进度条 -->
      <el-table-column label="解析状态" min-width="150" align="center">
        <template #default="{ row }">
          <template v-if="!row.is_directory && row.parse_status">
            <el-tooltip
              v-if="row.parse_status === ParseStatus.FAILED && row.error_message"
              :content="row.error_message" placement="top"
            >
              <el-tag size="small" :type="parseStatusOptions[row.parse_status]?.tag ?? 'info'">
                {{ parseStatusOptions[row.parse_status]?.label ?? row.parse_status }}
              </el-tag>
            </el-tooltip>
            <div v-else flex flex-col items-center gap-1>
              <el-tag size="small" :type="parseStatusOptions[row.parse_status]?.tag ?? 'info'">
                <el-icon v-if="row.parse_status === ParseStatus.PARSING" class="is-loading" :size="12" mr-0.5>
                  <Loading />
                </el-icon>
                {{ parseStatusOptions[row.parse_status]?.label ?? row.parse_status }}
                <span v-if="row.parse_status === ParseStatus.COMPLETED && row.chunk_count">
                  ({{ row.chunk_count }}块)
                </span>
              </el-tag>
              <!-- 入库步骤进度(待解析/解析中实时展示) -->
              <template v-if="row.parse_status !== ParseStatus.COMPLETED && ingestProgressMap[row.document_id]">
                <el-progress
                  :percentage="Math.round(ingestProgressMap[row.document_id]!.progress)"
                  :stroke-width="6" :show-text="false" w-full
                />
                <span text-2xs text-note-sub>{{ progressHint(ingestProgressMap[row.document_id]!) }}</span>
              </template>
            </div>
          </template>
          <span v-else text-note-sub>-</span>
        </template>
      </el-table-column>
      <el-table-column label="大小" min-width="100" align="center">
        <template #default="{ row }">
          {{ row.is_directory ? '-' : formatSize(row.file_size_bytes) }}
        </template>
      </el-table-column>
      <el-table-column label="描述" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.description || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="修改时间" min-width="120" align="center">
        <template #default="{ row }">
          {{ formatDate(row.updated_at || row.created_at) }}
        </template>
      </el-table-column>
      <!-- 操作列: 目录行=打开/重命名/删除; 文件行=文档操作(需 document_id, 旧数据未登记时仅展示提示) -->
      <el-table-column label="操作" min-width="280" align="center" :fixed="isMd ? 'right' : false">
        <template #default="{ row }">
          <template v-if="row.is_directory">
            <el-button size="small" type="primary" plain @click="handleOpen(row)">打开</el-button>
            <el-button size="small" type="success" plain @click="handleRenameFolder(row)">重命名</el-button>
            <el-button size="small" type="danger" plain @click="handleDeleteFolder(row)">删除</el-button>
          </template>
          <template v-else-if="row.document_id">
            <el-button size="small" type="primary" plain @click="handleDownload(row)">下载</el-button>
            <el-button size="small" type="warning" plain @click="handleReparse(row)">重新解析</el-button>
            <el-button size="small" plain @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" plain @click="handleDelete(row)">删除</el-button>
          </template>
          <span v-else text-note-sub text-xs>旧数据(未登记文档)</span>
        </template>
      </el-table-column>
    </el-table>

    <!-- 空状态提示 -->
    <div v-if="!loading && entries.length === 0" py-16 flex flex-col items-center text-note-sub>
      <el-icon text-5xl mb-3><FolderOpened /></el-icon>
      <p m-0 v-if="projectId">当前文件夹为空，可上传文档或新建文件夹</p>
      <p m-0 v-else>缺少项目参数，请从知识库页面进入</p>
    </div>

    <!-- 分页(手机居中, 桌面靠右) -->
    <div mt-4 flex flex-wrap justify-center sm:justify-end>
      <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.size"
        :total="total" layout="total, prev, pager, next"
        @size-change="() => fetchData()" @current-change="() => fetchData()" />
    </div>

    <!-- 新建文件夹对话框 -->
    <el-dialog v-model="folderDialogVisible" title="新建文件夹" width="90%" class="max-w-[420px]">
      <el-form :model="folderForm" :rules="nameRules" ref="folderFormRef" label-width="80px" @submit.prevent>
        <el-form-item label="文件夹名" prop="name">
          <el-input v-model="folderForm.name" placeholder="请输入文件夹名称" maxlength="255" @keyup.enter="handleFolderSubmit" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span>
          <el-button @click="folderDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleFolderSubmit" :loading="submitting">确认</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 编辑对话框(文件=文档元数据; 目录=重命名文件夹, 同一对话框分模式复用) -->
    <el-dialog :title="editMode === 'folder' ? '重命名文件夹' : '编辑文档'" v-model="dialogVisible" width="90%"
      class="max-w-[480px]">
      <el-form :model="form" :rules="nameRules" ref="formRef" label-width="80px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入名称" maxlength="255" />
        </el-form-item>
        <el-form-item v-if="editMode === 'file'" label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="请输入描述" maxlength="500" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span>
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSubmit" :loading="submitting">确认</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import {
  Back, Upload, Document, Folder, FolderOpened, FolderAdd, Loading, Search,
} from '@element-plus/icons-vue'
import {
  uploadRagDocument,
  listRagEntries,
  createRagFolder,
  renameRagFolder,
  deleteRagFolder,
  getRagDocumentDownloadUrl,
  getRagDocumentIngestProgress,
  updateRagDocument,
  deleteRagDocument,
  reparseRagDocumentTask,
  checkRagParseModels,
  type RagFileEntry,
} from '../api/document'
import { listRagProjects } from '../api/project'
import { ParseStatus, IngestStepState, parseStatusOptions } from '../types'
import type { DocumentIngestProgress } from '../types'
import type { PaginationParams } from '@/common/types/common'
import { useResponsive } from '@/common/composables/useResponsive'
import { ElMessage, ElMessageBox, type FormInstance, type UploadRawFile } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

// 断点状态(操作列固定策略)
const { isMd } = useResponsive()

// 路径参数中的项目ID
const projectId = computed(() => (route.query.project_id as string) || '')
const projectName = ref('知识库文档')

// 面包屑目录栈(项目根=根节点, 子目录逐级入栈)
const breadcrumbs = ref<{ id: string; name: string }[]>([])
// 当前父目录ID(空表示项目根文件夹)
const currentPid = computed(() =>
  breadcrumbs.value.length ? breadcrumbs.value[breadcrumbs.value.length - 1].id : undefined
)

// 分页参数
const pagination = ref<PaginationParams>({ page: 1, size: 20 })
const total = ref(0)
const loading = ref(false)
const uploading = ref(false)
const submitting = ref(false)
const searchQuery = ref('')

// 列表数据(目录+文件条目)
const entries = ref<RagFileEntry[]>([])

// 名称校验规则(目录与文档通用, 禁止路径非法字符)
const nameRules = {
  name: [
    { required: true, message: '请输入名称', trigger: 'blur' },
    { pattern: /^[^/\\:*?"<>|]+$/, message: '名称不能包含 / \\ : * ? " < > | 字符', trigger: 'blur' },
  ],
}

// 文件图标按扩展名着色
const fileIconClass = (ext: string) => {
  const e = (ext || '').toLowerCase()
  if (['pdf'].includes(e)) return 'text-red-500'
  if (['doc', 'docx'].includes(e)) return 'text-blue-500'
  if (['xls', 'xlsx', 'csv'].includes(e)) return 'text-green-500'
  if (['ppt', 'pptx'].includes(e)) return 'text-orange-500'
  return 'text-note-sub'
}

// 文件大小格式化
const formatSize = (bytes: number | null) => {
  if (!bytes) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`
}

// 日期格式化
const formatDate = (value: string) => {
  if (!value) return '-'
  return new Date(value).toLocaleDateString()
}

// 加载项目名称(面包屑根节点展示)
const loadProjectName = async () => {
  if (!projectId.value) return
  try {
    const res = await listRagProjects({ page: 1, size: 200 })
    const found = res.items.find((p) => p.id === projectId.value)
    if (found) projectName.value = found.name
  } catch {
    // 名称加载失败不影响列表展示
  }
}

// 获取当前目录条目列表(服务端名称过滤; 静默模式供轮询使用)
const fetchData = async (silent = false) => {
  if (!projectId.value) return
  try {
    if (!silent) loading.value = true
    const res = await listRagEntries(projectId.value, {
      ...pagination.value,
      pid: currentPid.value,
      name: searchQuery.value.trim() || undefined,
    })
    entries.value = res.items
    total.value = res.total
    // 拉取待解析/解析中文档的入库步骤进度(与列表同频刷新)
    await fetchIngestProgress()
  } catch (error) {
    console.error('获取目录内容失败:', error)
    if (!silent) ElMessage.error('获取目录内容失败')
  } finally {
    if (!silent) loading.value = false
  }
}

// 搜索防抖(300ms)
let searchTimer: ReturnType<typeof setTimeout> | undefined
const handleSearchDebounced = () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    pagination.value.page = 1
    fetchData()
  }, 300)
}

// 入库步骤进度缓存(键为文档ID)
const ingestProgressMap = ref<Record<string, DocumentIngestProgress>>({})

/** 拉取活跃文档的入库步骤进度(单个失败静默, 不影响列表展示) */
const fetchIngestProgress = async () => {
  const activeIds = entries.value
    .filter(
      (e) =>
        !e.is_directory &&
        e.document_id &&
        (e.parse_status === ParseStatus.PENDING || e.parse_status === ParseStatus.PARSING)
    )
    .map((e) => e.document_id!) as string[]
  // 清理已完成/已删除文档的进度缓存
  for (const key of Object.keys(ingestProgressMap.value)) {
    if (!activeIds.includes(key)) delete ingestProgressMap.value[key]
  }
  await Promise.all(
    activeIds.map(async (id) => {
      try {
        ingestProgressMap.value[id] = await getRagDocumentIngestProgress(id)
      } catch {
        // 进度获取失败不影响列表
      }
    })
  )
}

/** 进度提示文案: 优先当前执行中步骤的描述, 否则取最近的阶段描述 */
const progressHint = (p: DocumentIngestProgress) => {
  const running = p.steps.find((s) => s.status === IngestStepState.RUNNING)
  if (running?.message) return running.message
  if (p.parse_status === ParseStatus.PENDING) return '等待调度'
  const last = [...p.steps].reverse().find((s) => s.enabled && s.message)
  return last?.message ?? ''
}

/* ===== 解析状态轮询 =====
   存在 pending/parsing 文档时每 5s 静默刷新, 全部完成后自动停止 */
let pollTimer: ReturnType<typeof setInterval> | null = null

const hasParsingDoc = computed(() =>
  entries.value.some(
    (e) =>
      !e.is_directory &&
      (e.parse_status === ParseStatus.PENDING || e.parse_status === ParseStatus.PARSING)
  )
)

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

watch(hasParsingDoc, (parsing) => {
  if (parsing && !pollTimer) {
    pollTimer = setInterval(() => fetchData(true), 5000)
  } else if (!parsing) {
    stopPolling()
  }
})

onUnmounted(stopPolling)

// 打开条目(目录进入子级, 文件忽略)
const handleOpen = (row: RagFileEntry) => {
  if (!row.is_directory) return
  breadcrumbs.value.push({ id: row.id, name: row.name })
  pagination.value.page = 1
  fetchData()
}

// 面包屑跳转(-1 表示项目根文件夹)
const handleGoto = (idx: number) => {
  breadcrumbs.value = idx < 0 ? [] : breadcrumbs.value.slice(0, idx + 1)
  pagination.value.page = 1
  fetchData()
}

// 上传文档到当前文件夹(统一存储上传流程; 返回 false 阻止 el-upload 默认行为)
const handleUpload = async (file: UploadRawFile) => {
  if (!projectId.value) {
    ElMessage.warning('缺少项目参数，请从知识库页面进入')
    return false
  }
  try {
    uploading.value = true
    const doc = await uploadRagDocument(projectId.value, file, undefined, currentPid.value)
    ElMessage.success(`文档"${file.name}"上传成功`)
    // 上传即解析: 后端推送解析任务前已校验模型, 缺失时通过 parse_task_warning 弹窗警告
    if (doc.parse_task_warning) {
      ElMessageBox.alert(doc.parse_task_warning, '解析模型未配置', {
        type: 'warning',
        confirmButtonText: '知道了',
      }).catch(() => {})
    }
    fetchData()
  } catch (error) {
    console.error('上传失败:', error)
    ElMessage.error(`文档"${file.name}"上传失败`)
  } finally {
    uploading.value = false
  }
  return false
}

// ---------------- 新建文件夹 ----------------
const folderDialogVisible = ref(false)
const folderFormRef = ref<FormInstance>()
const folderForm = reactive({ name: '' })

const handleCreateFolder = () => {
  folderForm.name = ''
  folderDialogVisible.value = true
}

const handleFolderSubmit = async () => {
  if (!folderFormRef.value || !projectId.value) return
  const valid = await folderFormRef.value.validate().catch(() => false)
  if (!valid) return
  try {
    submitting.value = true
    await createRagFolder(projectId.value, folderForm.name.trim(), currentPid.value)
    ElMessage.success('文件夹创建成功')
    folderDialogVisible.value = false
    fetchData()
  } catch (error) {
    console.error('创建文件夹失败:', error)
    ElMessage.error(error instanceof Error ? error.message : '创建文件夹失败')
  } finally {
    submitting.value = false
  }
}

// ---------------- 删除文件夹 ----------------
const handleDeleteFolder = async (row: RagFileEntry) => {
  if (!projectId.value) return
  try {
    await ElMessageBox.confirm(
      `确定删除文件夹"${row.name}"吗？文件夹下全部内容将一并删除。`,
      '警告',
      { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' }
    )
    await deleteRagFolder(projectId.value, row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (error) {
    console.log('取消删除或删除失败:', error)
  }
}

// ---------------- 编辑(文件=文档元数据 / 目录=重命名) ----------------
const dialogVisible = ref(false)
const editMode = ref<'file' | 'folder'>('file')
const formRef = ref<FormInstance>()
const form = reactive({ name: '', description: '' })
const currentEntry = ref<RagFileEntry | null>(null)

const handleEdit = (row: RagFileEntry) => {
  editMode.value = 'file'
  currentEntry.value = row
  Object.assign(form, { name: row.name, description: row.description || '' })
  dialogVisible.value = true
}

const handleRenameFolder = (row: RagFileEntry) => {
  editMode.value = 'folder'
  currentEntry.value = row
  Object.assign(form, { name: row.name, description: '' })
  dialogVisible.value = true
}

const handleSubmit = async () => {
  if (!formRef.value || !currentEntry.value || !projectId.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  try {
    submitting.value = true
    if (editMode.value === 'folder') {
      await renameRagFolder(projectId.value, currentEntry.value.id, form.name.trim())
    } else if (currentEntry.value.document_id) {
      await updateRagDocument(currentEntry.value.document_id, {
        name: form.name.trim(),
        description: form.description,
      })
    }
    ElMessage.success('更新成功')
    dialogVisible.value = false
    fetchData()
  } catch (error) {
    console.error('更新失败:', error)
    ElMessage.error(error instanceof Error ? error.message : '更新失败')
  } finally {
    submitting.value = false
  }
}

// ---------------- 文档级操作(下载/重新解析/删除, 均以 document_id 为准) ----------------

// 下载文档(打开新窗口触发后端下载)
const handleDownload = (row: RagFileEntry) => {
  if (!row.document_id) return
  window.open(getRagDocumentDownloadUrl(row.document_id), '_blank')
}

// 重新解析文档(异步任务队列; 推送任务前先校验所需模型, 缺失时弹窗警告)
const handleReparse = async (row: RagFileEntry) => {
  if (!row.document_id) return
  try {
    // 模型预检: 对话/向量化模型缺失时弹窗警告并终止入队
    const check = await checkRagParseModels()
    if (!check.ok) {
      ElMessageBox.alert(check.message || '解析所需模型未配置', '解析模型未配置', {
        type: 'warning',
        confirmButtonText: '知道了',
      }).catch(() => {})
      return
    }
    await ElMessageBox.confirm(
      `确定重新解析文档"${row.name}"吗？将重建向量索引。`,
      '提示',
      { type: 'info', confirmButtonText: '确定', cancelButtonText: '取消' }
    )
    await reparseRagDocumentTask(row.document_id)
    ElMessage.success('已提交重新解析任务')
    // 刷新列表(状态变为解析中, 轮询自动接管跟踪进度)
    fetchData()
  } catch (error) {
    console.log('取消或失败:', error)
  }
}

// 删除文档(物理文件与向量数据一并删除)
const handleDelete = async (row: RagFileEntry) => {
  if (!row.document_id) return
  try {
    await ElMessageBox.confirm(
      `确定删除文档"${row.name}"吗？物理文件与向量数据将一并删除。`,
      '警告',
      { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' }
    )
    await deleteRagDocument(row.document_id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (error) {
    console.log('取消删除或删除失败:', error)
  }
}

onMounted(() => {
  loadProjectName()
  fetchData()
})

// 项目参数变化时刷新
watch(projectId, () => {
  pagination.value.page = 1
  breadcrumbs.value = []
  loadProjectName()
  fetchData()
})
</script>
