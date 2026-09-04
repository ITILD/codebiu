<template>
  <div p-4 md:p-6 w-full flex flex-col gap-4>
    <!-- 状态统计卡片(轮询刷新): 手机 2 列 / 平板及以上 4 列 -->
    <div grid grid-cols-2 md:grid-cols-4 gap-3>
      <div
        v-for="card in statCards" :key="card.status"
        cursor-pointer rounded-lg p-3
        bg-note-card border border-note shadow-note
        transition-colors hover:bg-note-tint
        :class="{ 'ring-2 ring-note': queryParams.status === card.status }"
        @click="handleStatCardClick(card.status)"
      >
        <div text-xs text-note-sub>{{ card.label }}</div>
        <div text-2xl font-bold mt-1 :class="card.color">{{ card.value }}</div>
      </div>
    </div>

    <!-- 工具栏: 搜索 + 自动刷新 + 新建 -->
    <div flex flex-wrap items-center gap-3>
      <TableSearchBar
        v-model="queryParams"
        :fields="searchFields"
        :collapse-count="2"
        @search="handleSearch"
        @reset="handleSearch"
      />
      <el-tooltip content="存在活跃任务时每 3 秒自动刷新状态与进度" placement="top">
        <div flex items-center gap-1>
          <span text-xs text-note-sub>自动刷新</span>
          <el-switch v-model="autoRefresh" />
        </div>
      </el-tooltip>
      <div flex-1 />
      <el-button type="primary" @click="openCreateDialog">
        <el-icon mr-1><Plus /></el-icon>新建任务
      </el-button>
    </div>

    <!-- 任务表格 -->
    <el-table :data="tableData" v-loading="loading" stripe w-full>
      <el-table-column prop="name" label="任务名称" min-width="130" show-overflow-tooltip />
      <el-table-column label="类型" width="130" show-overflow-tooltip>
        <template #default="{ row }">
          {{ typeName(row.task_type) }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="statusTagTypes[row.status as TaskStatus] ?? 'info'" size="small" effect="light">
            {{ statusLabels[row.status as TaskStatus] ?? row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <!-- 完成百分比(轮询实时推进) -->
      <el-table-column label="进度" width="170">
        <template #default="{ row }">
          <div flex items-center gap-2>
            <el-progress
              class="flex-1"
              :percentage="Math.round(row.progress)"
              :stroke-width="8"
              :status="progressStatus(row.status)"
            />
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="message" label="当前阶段" min-width="150" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.message ?? '-' }}
        </template>
      </el-table-column>
      <!-- Celery 侧状态对照(broker/backend 真实状态) -->
      <el-table-column label="Celery" width="100" align="center">
        <template #default="{ row }">
          <el-tooltip v-if="row.celery_progress != null" :content="`Celery 侧进度 ${row.celery_progress}%`" placement="top">
            <span text-xs>{{ row.celery_state ?? '-' }} {{ Math.round(row.celery_progress) }}%</span>
          </el-tooltip>
          <span v-else text-xs text-note-sub>{{ row.celery_state ?? '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="100" show-overflow-tooltip>
        <template #default="{ row }">
          {{ formatTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="190" align="center">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
          <el-button
            v-if="row.status === 'pending' || row.status === 'running'"
            link type="warning" size="small" @click="handleCancel(row)"
          >
            取消
          </el-button>
          <el-button
            v-if="isFinished(row)"
            link type="primary" size="small" @click="handleRetry(row)"
          >
            重试
          </el-button>
          <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div flex justify-end>
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.size"
        :total="total"
        layout="total, prev, pager, next"
        @size-change="fetchData"
        @current-change="fetchData"
      />
    </div>

    <!-- 新建任务对话框(参数 JSON + 默认模板) -->
    <el-dialog v-model="createDialogVisible" title="新建任务" width="90%" class="max-w-[560px]">
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="80px">
        <el-form-item label="任务类型" prop="task_type">
          <el-select v-model="createForm.task_type" placeholder="请选择任务类型" @change="handleTypeChange">
            <el-option
              v-for="t in registry" :key="t.type"
              :label="t.name" :value="t.type"
            />
          </el-select>
          <div v-if="currentTypeDef" text-xs text-note-sub mt-1>{{ currentTypeDef.description }}</div>
        </el-form-item>
        <el-form-item label="任务名称" prop="name">
          <el-input v-model="createForm.name" placeholder="请输入任务名称" maxlength="200" />
        </el-form-item>
        <el-form-item label="参数 JSON" prop="payloadText">
          <div w-full flex flex-col gap-1>
            <div flex items-center gap-2>
              <el-button size="small" text type="primary" @click="fillDefaultPayload">
                载入默认模板
              </el-button>
              <span text-xs text-note-sub>提交前会校验 JSON 格式</span>
            </div>
            <el-input
              v-model="createForm.payloadText"
              type="textarea" :rows="7"
              placeholder='{"key": "value"}'
              class="font-mono"
            />
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleCreate">提交任务</el-button>
      </template>
    </el-dialog>

    <!-- 任务详情抽屉(参数/结果 JSON + Celery 对照) -->
    <el-drawer v-model="detailVisible" title="任务详情" size="420px">
      <template v-if="detailTask">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="ID">
            <span break-all font-mono text-xs>{{ detailTask.id }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="名称">{{ detailTask.name }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ typeName(detailTask.task_type) }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTagTypes[detailTask.status] ?? 'info'" size="small">
              {{ statusLabels[detailTask.status] ?? detailTask.status }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="进度">
            <el-progress
              :percentage="Math.round(detailTask.progress)"
              :stroke-width="10"
              :status="progressStatus(detailTask.status)"
            />
          </el-descriptions-item>
          <el-descriptions-item label="当前阶段">{{ detailTask.message ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="Celery 对照">
            {{ detailTask.celery_state ?? '-' }}
            <span v-if="detailTask.celery_progress != null">/ {{ Math.round(detailTask.celery_progress) }}%</span>
          </el-descriptions-item>
          <el-descriptions-item label="Celery ID">
            <span break-all font-mono text-xs>{{ detailTask.celery_task_id ?? '-' }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatTime(detailTask.created_at, true) }}</el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ formatTime(detailTask.started_at, true) }}</el-descriptions-item>
          <el-descriptions-item label="结束时间">{{ formatTime(detailTask.finished_at, true) }}</el-descriptions-item>
        </el-descriptions>

        <!-- 失败原因 -->
        <el-alert
          v-if="detailTask.error" type="error" :closable="false" show-icon mt-3
          :title="detailTask.error"
        />

        <!-- 同步校正(worker 回写中断时使用) -->
        <div flex justify-end mt-2>
          <el-button size="small" text type="primary" :loading="submitting" @click="handleSync">
            从 Celery 同步状态
          </el-button>
        </div>

        <!-- 参数 / 结果 JSON -->
        <div mt-3 flex flex-col gap-2>
          <div text-sm text-note>任务参数</div>
          <pre
            max-h-48 overflow-auto rounded-md p-2 text-xs font-mono leading-5
            bg-note-tint border border-note
          >{{ pretty(detailTask.payload) }}</pre>
          <template v-if="detailTask.result">
            <div text-sm text-note>执行结果</div>
            <pre
              max-h-48 overflow-auto rounded-md p-2 text-xs font-mono leading-5
              bg-note-tint border border-note
            >{{ pretty(detailTask.result) }}</pre>
          </template>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import TableSearchBar, { type SearchField } from '@/common/components/TableSearchBar.vue'
import {
  cancelTask,
  createTask,
  deleteTask,
  getTask,
  getTaskRegistry,
  getTaskStats,
  listTasks,
  retryTask,
  syncTask,
} from '../api/task'
import {
  statusLabels,
  statusOptions,
  statusTagTypes,
  type QueueTask,
  type TaskStats,
  type TaskStatus,
  type TagType,
  type TaskTypeDef,
} from '../types'
import type { PaginationParams, PaginationResponse } from '@/common/types/common'

// ################ 统计概览 ################
const stats = ref<TaskStats>({ total: 0, pending: 0, running: 0, success: 0, failed: 0, cancelled: 0 })

/** 概览卡片配置(点击可按状态筛选) */
const statCards = computed(() => [
  { status: '', label: '全部任务', value: stats.value.total, color: 'text-note' },
  { status: 'pending', label: '排队中', value: stats.value.pending, color: 'text-note-sub' },
  { status: 'running', label: '执行中', value: stats.value.running, color: 'text-blue-500' },
  { status: 'success', label: '成功', value: stats.value.success, color: 'text-green-600' },
  { status: 'failed', label: '失败', value: stats.value.failed, color: 'text-red-500' },
  { status: 'cancelled', label: '已取消', value: stats.value.cancelled, color: 'text-orange-400' },
])

/** 点击统计卡片: 切换状态过滤并刷新 */
const handleStatCardClick = (status: string) => {
  queryParams.value.status = status || undefined
  pagination.value.page = 1
  fetchData()
}

// ################ 类型注册表 ################
const registry = ref<TaskTypeDef[]>([])

/** 类型编码转显示名 */
const typeName = (type: string) => registry.value.find(t => t.type === type)?.name ?? type

// ################ 列表与查询 ################
const loading = ref(false)
const tableData = ref<QueueTask[]>([])
const total = ref(0)
const pagination = ref<PaginationParams>({ page: 1, size: 10 })

// 搜索字段配置(名称/类型/状态)
const searchFields: SearchField[] = [
  { prop: 'keyword', label: '名称' },
  {
    prop: 'task_type', label: '类型', type: 'select',
    options: [], // 挂载后由注册表填充
  },
  { prop: 'status', label: '状态', type: 'select', options: statusOptions },
]
// 查询参数(与后端列表接口过滤参数对齐)
const queryParams = ref<Record<string, unknown>>({
  keyword: '',
  task_type: undefined,
  status: undefined,
})

/** 获取任务列表 */
const fetchData = async () => {
  try {
    loading.value = true
    const { keyword, task_type, status } = queryParams.value
    const res: PaginationResponse<QueueTask> = await listTasks({
      ...pagination.value,
      keyword: (keyword as string) || undefined,
      task_type: (task_type as string) || undefined,
      status: (status as string) || undefined,
    })
    tableData.value = res.items
    total.value = res.total
  }
  catch (error) {
    console.error('获取任务列表失败:', error)
    ElMessage.error('获取任务列表失败')
  }
  finally {
    loading.value = false
  }
}

/** 搜索/重置: 回到第一页后重新查询 */
const handleSearch = () => {
  pagination.value.page = 1
  fetchData()
}

/** 获取状态统计 */
const fetchStats = async () => {
  try {
    stats.value = await getTaskStats()
  }
  catch (error) {
    console.error('获取任务统计失败:', error)
  }
}

/** 刷新列表 + 统计 */
const refreshAll = async () => {
  await Promise.all([fetchData(), fetchStats()])
}

// ################ 轮询 ################
const autoRefresh = ref(true)
let pollTimer: number | undefined

/** 是否存在活跃任务(排队/执行中) */
const hasActive = computed(() =>
  tableData.value.some(t => t.status === 'pending' || t.status === 'running'),
)

// 自动刷新开关: 活跃期间每 3 秒轮询(无活跃任务时自动降频到 10 秒仅刷统计)
watch([autoRefresh, hasActive], setupPolling, { immediate: true })

function setupPolling() {
  window.clearInterval(pollTimer)
  pollTimer = undefined
  if (!autoRefresh.value) return
  const interval = hasActive.value ? 3000 : 10000
  pollTimer = window.setInterval(() => {
    // 活跃期间整表刷新, 空闲时仅刷统计(降低数据库压力)
    if (hasActive.value) fetchData()
    else fetchStats()
  }, interval)
}

onBeforeUnmount(() => window.clearInterval(pollTimer))

// ################ 新建任务 ################
const createDialogVisible = ref(false)
const createFormRef = ref<FormInstance>()
const submitting = ref(false)
const createForm = ref({
  task_type: '',
  name: '',
  payloadText: '',
})

const createRules = {
  task_type: [{ required: true, message: '请选择任务类型', trigger: 'change' }],
  name: [
    { required: true, message: '请输入任务名称', trigger: 'blur' },
    { min: 1, max: 200, message: '长度在 1 到 200 个字符', trigger: 'blur' },
  ],
  payloadText: [
    {
      validator: (_rule: unknown, value: string, callback: (err?: Error) => void) => {
        if (!value.trim()) return callback()
        try {
          JSON.parse(value)
          callback()
        }
        catch {
          callback(new Error('JSON 格式不合法'))
        }
      },
      trigger: 'blur',
    },
  ],
}

/** 当前选中的类型定义 */
const currentTypeDef = computed(() =>
  registry.value.find(t => t.type === createForm.value.task_type),
)

/** 打开新建对话框(重置表单) */
const openCreateDialog = () => {
  createForm.value = { task_type: '', name: '', payloadText: '' }
  createDialogVisible.value = true
}

/** 切换类型: 自动填充默认名称与参数模板 */
const handleTypeChange = (type: string) => {
  const def = registry.value.find(t => t.type === type)
  if (!def) return
  createForm.value.name = `${def.name}-${timeTag()}`
  createForm.value.payloadText = JSON.stringify(def.default_payload, null, 2)
}

/** 载入默认参数模板 */
const fillDefaultPayload = () => {
  if (!currentTypeDef.value) {
    ElMessage.warning('请先选择任务类型')
    return
  }
  createForm.value.payloadText = JSON.stringify(currentTypeDef.value.default_payload, null, 2)
}

/** 时间戳(默认任务命名用) */
const timeTag = () => {
  const now = new Date()
  return `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`
}

/** 提交创建(参数 JSON 校验通过后投递队列) */
const handleCreate = async () => {
  const valid = await createFormRef.value?.validate().catch(() => false)
  if (!valid) return
  let payload: Record<string, unknown> = {}
  if (createForm.value.payloadText.trim()) {
    try {
      payload = JSON.parse(createForm.value.payloadText)
    }
    catch {
      ElMessage.error('参数 JSON 格式不合法')
      return
    }
  }
  try {
    submitting.value = true
    await createTask({
      name: createForm.value.name,
      task_type: createForm.value.task_type,
      payload,
    })
    ElMessage.success('任务已提交到队列')
    createDialogVisible.value = false
    await refreshAll()
  }
  catch (error) {
    console.error('创建任务失败:', error)
    ElMessage.error('创建任务失败')
  }
  finally {
    submitting.value = false
  }
}

// ################ 行操作 ################

/** 任务是否已结束(可重试) */
const isFinished = (row: QueueTask) =>
  !['pending', 'running'].includes(row.status)

/** 进度条状态色 */
const progressStatus = (status: TaskStatus) =>
  status === 'success' ? 'success' : status === 'failed' ? 'exception' : undefined

/** 时间格式化 */
const formatTime = (value: string | null | undefined, withDate = false) => {
  if (!value) return '-'
  const opt: Intl.DateTimeFormatOptions = withDate
    ? { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' }
    : { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }
  return new Date(value).toLocaleString('zh-CN', opt)
}

/** JSON 美化(详情展示用) */
const pretty = (value: unknown) => JSON.stringify(value, null, 2)

// ################ 详情抽屉 ################
const detailVisible = ref(false)
const detailTask = ref<QueueTask | null>(null)

/** 打开详情(拉取最新数据) */
const openDetail = async (row: QueueTask) => {
  try {
    detailTask.value = await getTask(row.id)
    detailVisible.value = true
  }
  catch (error) {
    console.error('获取任务详情失败:', error)
    ElMessage.error('获取任务详情失败')
  }
}

/** 从 Celery 结果后端同步状态 */
const handleSync = async () => {
  if (!detailTask.value) return
  try {
    submitting.value = true
    detailTask.value = await syncTask(detailTask.value.id)
    ElMessage.success('状态已同步')
    await fetchData()
  }
  catch (error) {
    console.error('同步状态失败:', error)
    ElMessage.error('同步状态失败')
  }
  finally {
    submitting.value = false
  }
}

/** 取消任务(确认后 revoke + 置 cancelled) */
const handleCancel = (row: QueueTask) => {
  ElMessageBox.confirm(`确定取消任务「${row.name}」吗?`, '取消确认', {
    type: 'warning', confirmButtonText: '取消任务', cancelButtonText: '返回',
  })
    .then(async () => {
      try {
        await cancelTask(row.id)
        ElMessage.success('任务已取消')
        await refreshAll()
      }
      catch (error) {
        console.error('取消任务失败:', error)
        ElMessage.error('取消任务失败')
      }
    })
    .catch(() => {})
}

/** 重试任务(重置进度重新入队) */
const handleRetry = async (row: QueueTask) => {
  try {
    await retryTask(row.id)
    ElMessage.success('任务已重新入队')
    await refreshAll()
  }
  catch (error) {
    console.error('重试任务失败:', error)
    ElMessage.error('重试任务失败')
  }
}

/** 删除任务(确认后删除记录) */
const handleDelete = (row: QueueTask) => {
  ElMessageBox.confirm(
    `确定删除任务「${row.name}」吗? 删除后不可恢复。`,
    '删除确认',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  )
    .then(async () => {
      try {
        await deleteTask(row.id)
        ElMessage.success('删除成功')
        // 处理空页情况
        if (tableData.value.length === 1 && pagination.value.page > 1) {
          pagination.value.page -= 1
        }
        await refreshAll()
      }
      catch (error) {
        console.error('删除任务失败:', error)
        ElMessage.error('删除任务失败')
      }
    })
    .catch(() => {})
}

// ################ 生命周期 ################
onMounted(async () => {
  // 加载任务类型注册表(搜索下拉 + 新建对话框)
  try {
    registry.value = await getTaskRegistry()
    searchFields[1].options = registry.value.map(t => ({ label: t.name, value: t.type }))
  }
  catch (error) {
    console.error('获取任务类型注册表失败:', error)
  }
  await refreshAll()
})
</script>
