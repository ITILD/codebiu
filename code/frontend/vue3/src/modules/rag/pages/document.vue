<template>
  <div p-2 w-full>
    <!-- 页头: 返回 + 项目名 + 上传 -->
    <div mb-4 flex flex-wrap items-center gap-2>
      <el-button :icon="Back" @click="router.push('/rag/project')" />
      <span font-bold text-lg>{{ projectName }}</span>
      <el-tag v-if="projectId" size="small">文档管理</el-tag>
      <div flex-1 />
      <el-upload :show-file-list="false" :before-upload="handleUpload" :disabled="uploading"
        accept=".txt,.md,.pdf,.docx,.xlsx,.pptx,.csv,.html,.json">
        <el-button type="primary" :loading="uploading" :icon="Upload">
          {{ uploading ? '上传中' : '上传文档' }}
        </el-button>
      </el-upload>
    </div>

    <!-- 统一搜索栏: 多字段筛选(名称/解析状态) -->
    <TableSearchBar
      v-model="queryParams"
      :fields="searchFields"
      :collapse-count="2"
      @search="handleSearch"
      @reset="handleSearch"
    />

    <!-- 文档表格 -->
    <el-table v-loading="loading" :data="documents" stripe w-full>
      <el-table-column label="文档名称" min-width="220" show-overflow-tooltip>
        <template #default="{ row }">
          <div flex items-center gap-2>
            <el-icon text-lg :class="fileIconClass(row.file_extension)"><Document /></el-icon>
            <span>{{ row.name }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="类型" width="90" align="center">
        <template #default="{ row }">
          <el-tag size="small" type="info">{{ (row.file_extension || '').toUpperCase() }}</el-tag>
        </template>
      </el-table-column>
      <!-- 解析状态: pending/parsing/completed/failed, 完成显示分块数, 失败悬浮原因 -->
      <el-table-column label="解析状态" width="130" align="center">
        <template #default="{ row }">
          <el-tooltip
            v-if="row.parse_status === ParseStatus.FAILED && row.error_message"
            :content="row.error_message" placement="top"
          >
            <el-tag size="small" :type="parseStatusOptions[row.parse_status]?.tag ?? 'info'">
              {{ parseStatusOptions[row.parse_status]?.label ?? row.parse_status }}
            </el-tag>
          </el-tooltip>
          <el-tag v-else size="small" :type="parseStatusOptions[row.parse_status]?.tag ?? 'info'">
            <el-icon v-if="row.parse_status === ParseStatus.PARSING" class="is-loading" :size="12" mr-0.5>
              <Loading />
            </el-icon>
            {{ parseStatusOptions[row.parse_status]?.label ?? row.parse_status }}
            <span v-if="row.parse_status === ParseStatus.COMPLETED && row.chunk_count">
              ({{ row.chunk_count }}块)
            </span>
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="大小" width="100" align="center">
        <template #default="{ row }">
          {{ formatSize(row.file_size_bytes) }}
        </template>
      </el-table-column>
      <el-table-column label="描述" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.description || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="上传时间" width="120" align="center">
        <template #default="{ row }">
          {{ formatDate(row.created_at) }}
        </template>
      </el-table-column>
      <!-- 操作列: 平板及以上固定右侧, 手机取消固定避免遮挡(表格自带横向滚动) -->
      <el-table-column label="操作" min-width="280" align="center" :fixed="isMd ? 'right' : false">
        <template #default="{ row }">
          <el-button size="small" type="primary" plain @click="handleDownload(row)">下载</el-button>
          <el-button size="small" type="warning" plain @click="handleReparse(row)">重新解析</el-button>
          <el-button size="small" plain @click="handleEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" plain @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 空状态提示 -->
    <div v-if="!loading && documents.length === 0" py-16 flex flex-col items-center text-gray-4>
      <el-icon text-5xl mb-3><FolderOpened /></el-icon>
      <p m-0 v-if="projectId">暂无文档，点击右上角"上传文档"开始</p>
      <p m-0 v-else>缺少项目参数，请从知识库页面进入</p>
    </div>

    <!-- 分页(手机居中, 桌面靠右) -->
    <div mt-4 flex flex-wrap justify-center sm:justify-end>
      <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.size"
        :total="total" layout="total, prev, pager, next"
        @size-change="() => fetchData()" @current-change="() => fetchData()" />
    </div>

    <!-- 编辑对话框 -->
    <el-dialog v-model="dialogVisible" title="编辑文档" width="90%" class="max-w-[480px]">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入文档名称" maxlength="200" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
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
import { Back, Upload, Document, FolderOpened, Loading } from '@element-plus/icons-vue'
import {
  uploadRagDocument,
  listRagProjectDocuments,
  getRagDocumentDownloadUrl,
  updateRagDocument,
  deleteRagDocument,
  reparseRagDocument,
} from '../api/document'
import { listRagProjects } from '../api/project'
import { ParseStatus, parseStatusOptions } from '../types'
import type { ProjectDocument } from '../types'
import TableSearchBar, { type SearchField } from '@/common/components/TableSearchBar.vue'
import type { PaginationParams } from '@/common/types/common'
import { SysSettingStore } from '@/common/stores/sys'
import { ElMessage, ElMessageBox, type FormInstance, type UploadRawFile } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

// 断点状态(操作列固定策略)
const sysSettingStore = SysSettingStore()
const isMd = computed(() => sysSettingStore.sysStyle.isMd)

// 路径参数中的项目ID
const projectId = computed(() => (route.query.project_id as string) || '')
const projectName = ref('知识库文档')

// 分页参数
const pagination = ref<PaginationParams>({ page: 1, size: 20 })
const total = ref(0)
const loading = ref(false)
const uploading = ref(false)

// 搜索字段配置(名称/解析状态多字段筛选)
const searchFields: SearchField[] = [
  { prop: 'name', label: '文档名称' },
  {
    prop: 'parse_status', label: '解析状态', type: 'select',
    options: Object.entries(parseStatusOptions).map(([value, opt]) => ({
      label: opt.label, value,
    })),
  },
]
// 查询参数(与后端列表接口过滤参数对齐)
const queryParams = ref<Record<string, unknown>>({
  name: '',
  parse_status: undefined,
})

// 列表数据
const documents = ref<ProjectDocument[]>([])

// 编辑对话框
const dialogVisible = ref(false)
const submitting = ref(false)
const currentId = ref<string | null>(null)
const formRef = ref<FormInstance>()
const form = reactive({ name: '', description: '' })

const rules = {
  name: [{ required: true, message: '请输入文档名称', trigger: 'blur' }],
}

// 文件图标按扩展名着色
const fileIconClass = (ext: string) => {
  const e = ext.toLowerCase()
  if (['pdf'].includes(e)) return 'text-red-5'
  if (['doc', 'docx'].includes(e)) return 'text-blue-5'
  if (['xls', 'xlsx', 'csv'].includes(e)) return 'text-green-5'
  if (['ppt', 'pptx'].includes(e)) return 'text-orange-5'
  return 'text-gray-5'
}

// 文件大小格式化
const formatSize = (bytes: number) => {
  if (!bytes) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`
}

// 日期格式化
const formatDate = (value: string) => new Date(value).toLocaleDateString()

// 加载项目名称
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

// 获取文档列表(携带多字段过滤参数; 静默模式供轮询使用, 不显示 loading/错误提示)
const fetchData = async (silent = false) => {
  if (!projectId.value) return
  try {
    if (!silent) loading.value = true
    const { name, parse_status } = queryParams.value
    const res = await listRagProjectDocuments(projectId.value, {
      ...pagination.value,
      name: (name as string) || undefined,
      parse_status: (parse_status as string) || undefined,
    })
    documents.value = res.items
    total.value = res.total
  } catch (error) {
    console.error('获取文档列表失败:', error)
    if (!silent) ElMessage.error('获取文档列表失败')
  } finally {
    if (!silent) loading.value = false
  }
}

/** 搜索/重置: 回到第一页后重新查询 */
const handleSearch = () => {
  pagination.value.page = 1
  fetchData()
}

/* ===== 解析状态轮询 =====
   存在 pending/parsing 文档时每 5s 静默刷新, 全部完成后自动停止 */
let pollTimer: ReturnType<typeof setInterval> | null = null

const hasParsingDoc = computed(() =>
  documents.value.some(
    (d) => d.parse_status === ParseStatus.PENDING || d.parse_status === ParseStatus.PARSING,
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

// 上传文档(返回 false 阻止 el-upload 默认行为)
const handleUpload = async (file: UploadRawFile) => {
  if (!projectId.value) {
    ElMessage.warning('缺少项目参数，请从知识库页面进入')
    return false
  }
  try {
    uploading.value = true
    await uploadRagDocument(projectId.value, file)
    ElMessage.success(`文档"${file.name}"上传成功`)
    fetchData()
  } catch (error) {
    console.error('上传失败:', error)
    ElMessage.error(`文档"${file.name}"上传失败`)
  } finally {
    uploading.value = false
  }
  return false
}

// 下载文档(打开新窗口触发后端下载)
const handleDownload = (row: ProjectDocument) => {
  window.open(getRagDocumentDownloadUrl(row.id), '_blank')
}

// 重新解析文档(异步任务)
const handleReparse = async (row: ProjectDocument) => {
  try {
    await ElMessageBox.confirm(
      `确定重新解析文档"${row.name}"吗？将重建向量索引。`,
      '提示',
      { type: 'info', confirmButtonText: '确定', cancelButtonText: '取消' }
    )
    await reparseRagDocument(row.id)
    ElMessage.success('已提交重新解析任务')
    // 刷新列表(状态变为解析中, 轮询自动接管跟踪进度)
    fetchData()
  } catch (error) {
    console.log('取消或失败:', error)
  }
}

// 打开编辑对话框
const handleEdit = (row: ProjectDocument) => {
  currentId.value = row.id
  Object.assign(form, {
    name: row.name,
    description: row.description || '',
  })
  dialogVisible.value = true
}

// 提交编辑
const handleSubmit = async () => {
  if (!formRef.value || !currentId.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  try {
    submitting.value = true
    await updateRagDocument(currentId.value, { ...form })
    ElMessage.success('文档更新成功')
    dialogVisible.value = false
    fetchData()
  } catch (error) {
    console.error('更新失败:', error)
    ElMessage.error('更新失败')
  } finally {
    submitting.value = false
  }
}

// 删除文档
const handleDelete = async (row: ProjectDocument) => {
  try {
    await ElMessageBox.confirm(
      `确定删除文档"${row.name}"吗？物理文件与向量数据将一并删除。`,
      '警告',
      { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' }
    )
    await deleteRagDocument(row.id)
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
  loadProjectName()
  fetchData()
})
</script>
