<template>
  <div p-4 md:p-6 w-full>
    <!-- 统一搜索栏: 多字段筛选 -->
    <TableSearchBar
      v-model="queryParams"
      :fields="searchFields"
      @search="handleSearch"
      @reset="handleSearch"
    >
      <template #actions>
        <el-button v-if="isAdmin" type="warning" plain :loading="revectorizing" @click="handleRevectorize">
          重建向量索引
        </el-button>
        <el-button type="primary" @click="handleCreate">新增模型配置</el-button>
      </template>
    </TableSearchBar>

    <!-- 数据表格(不生效模型整行灰显) -->
    <el-table :data="tableData" v-loading="loading" stripe w-full :row-class-name="inactiveRowClass">
      <el-table-column label="模型类型" min-width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="modelTypeTagType[row.model_type] ?? 'info'" size="small">
            {{ modelTypeLabel(row.model_type) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="服务方案" min-width="130" align="center">
        <template #default="{ row }">
          {{ serverTypeLabel(row.server_type) }}
        </template>
      </el-table-column>
      <el-table-column label="模型" min-width="200">
        <template #default="{ row }">
          <div flex flex-col>
            <div flex items-center gap-1>
              <span>{{ modelMainLabel(row) }}</span>
              <el-tag v-if="row.is_default" type="warning" size="small">默认</el-tag>
              <el-tag v-if="row.is_active === false" type="info" size="small">不生效</el-tag>
            </div>
            <div v-if="row.display_name && row.display_name !== row.model" text-xs text-note-sub>
              {{ row.model }}
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="URL" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.url || (canManage(row) ? '-' : '仅管理员可见') }}
        </template>
      </el-table-column>
      <el-table-column label="归属" min-width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="scopeTagType[row.scope] ?? 'info'" size="small">
            {{ scopeShortLabel(row.scope) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">
          {{ formatTime(row.updated_at) }}
        </template>
      </el-table-column>
      <!-- 操作列: 平板及以上固定右侧, 手机取消固定避免遮挡 -->
      <el-table-column label="操作" min-width="140" align="center" :fixed="isMd ? 'right' : false">
        <template #default="{ row }">
          <template v-if="canManage(row)">
            <el-button link type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
          <span v-else text-xs text-note-sub>仅查看</span>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页(手机居中, 桌面靠右) -->
    <div mt-4 flex flex-wrap justify-center sm:justify-end>
      <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.size"
        :total="total" layout="total, prev, pager, next"
        @size-change="fetchData" @current-change="fetchData" />
    </div>

    <!-- 编辑/创建对话框(按模型类型动态渲染参数) -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="90%" class="max-w-[640px]">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="110px">
        <!-- 模型类型 -->
        <el-form-item label="模型类型" prop="model_type">
          <el-select v-model="form.model_type" w-full @change="handleTypeChange">
            <el-option v-for="opt in modelTypeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>

        <!-- 服务方案(按类型过滤选项) -->
        <el-form-item label="服务方案" prop="server_type">
          <el-select v-model="form.server_type" w-full>
            <el-option v-for="opt in serverTypeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>

        <!-- 模型标识(API 类=模型名; 本地类=模型目录名/路径) -->
        <el-form-item :label="isLocalType ? '模型目录' : '模型标识'" prop="model">
          <el-input v-model="form.model"
            :placeholder="isLocalType ? '模型目录名(相对 voice 模型根目录)或绝对路径' : '如 qwen3-vl:235b'" />
        </el-form-item>

        <!-- 归属范围: 公共/部门/个人 -->
        <el-form-item label="归属范围" prop="scope">
          <el-radio-group v-model="form.scope" w-full>
            <el-radio v-for="opt in modelScopeOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.scope === ModelScope.PUBLIC" label="默认公共" prop="is_default">
          <el-switch v-model="form.is_default" active-text="设为该类默认模型" />
        </el-form-item>
        <!-- 是否生效(仅管理员): 停用的模型前端灰色显示且不可被使用 -->
        <el-form-item v-if="isAdmin" label="是否生效" prop="is_active">
          <el-switch v-model="form.is_active" active-text="生效" inactive-text="停用" />
        </el-form-item>

        <!-- 显示名称(用于区分同名但来源不同的模型) -->
        <el-form-item label="显示名称" prop="display_name">
          <el-input v-model="form.display_name"
            placeholder="可留空, 用于区分同名但不同来源/配置的模型" maxlength="100" />
        </el-form-item>

        <!-- API 类: url / api_key -->
        <template v-if="!isLocalType">
          <el-form-item label="API URL" prop="url">
            <el-input v-model="form.url" placeholder="https://api.openai.com/v1" />
          </el-form-item>
          <el-form-item label="API Key" prop="api_key">
            <el-input v-model="form.api_key" placeholder="sk-..." show-password />
          </el-form-item>
        </template>

        <!-- 对话模型参数 -->
        <template v-if="form.model_type === ModelType.CHAT">
          <el-form-item label="温度系数" prop="temperature">
            <el-input-number v-model="form.temperature" :min="0" :max="2" :step="0.1" w-full />
          </el-form-item>
          <el-form-item label="输入tokens" prop="input_tokens">
            <el-input-number v-model="form.input_tokens" :min="1" :step="1024" w-full />
          </el-form-item>
          <el-form-item label="输出tokens" prop="out_tokens">
            <el-input-number v-model="form.out_tokens" :min="1" :step="1024" w-full />
          </el-form-item>
          <el-form-item label="禁用思考" prop="no_think">
            <el-switch v-model="form.no_think" />
          </el-form-item>
        </template>

        <!-- 嵌入模型: 维度 -->
        <el-form-item v-if="form.model_type === ModelType.EMBEDDINGS" label="向量维度" prop="out_tokens">
          <el-input-number v-model="form.out_tokens" :min="1" :step="256" w-full />
        </el-form-item>

        <!-- 超时与成本(API 类) -->
        <template v-if="!isLocalType">
          <el-form-item label="超时(秒)" prop="timeout">
            <el-input-number v-model="form.timeout" :min="1" :max="600" w-full />
          </el-form-item>
          <el-form-item label="输入成本" prop="pay_in">
            <el-input-number v-model="form.pay_in" :min="0" :step="0.5" w-full />
          </el-form-item>
          <el-form-item label="输出成本" prop="pay_out">
            <el-input-number v-model="form.pay_out" :min="0" :step="0.5" w-full />
          </el-form-item>
        </template>

        <!-- 扩展配置(本地类: 模型路径/设备等; API 类也可放自定义参数) -->
        <el-form-item label="扩展配置" prop="extra_text">
          <div w-full flex flex-col gap-2>
            <el-input v-model="form.extra_text" type="textarea" :rows="4"
              placeholder='JSON 对象, 如 {"device": "cpu", "num_threads": 2}' />
            <div v-if="extraHints.length" text-xs text-note-sub leading-5>
              <div v-for="hint in extraHints" :key="hint">· {{ hint }}</div>
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">
          确认
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { createModelConfig, deleteModelConfig, updateModelConfig, getModelConfig, listModelConfigs, revectorizeChunks, getRevectorizeStatus } from '../api/model_config'
import type { PaginationParams, PaginationResponse } from '@/common/types/common'
import TableSearchBar, { type SearchField } from '@/common/components/TableSearchBar.vue'
import { useAuthStore } from '@/common/stores/auth'
import { useResponsive } from '@/common/composables/useResponsive'
import { usePermission } from '@/common/composables/usePermission'
import {
  ModelType,
  ModelScope,
  modelTypeOptions,
  modelTypeTagType,
  serverTypeOptionsFor,
  modelTypeLabel,
  serverTypeLabel,
  modelScopeOptions,
  scopeShortLabel,
  modelMainLabel,
  extraKeyHints,
  type ModelConfig,
  type ModelConfigCreate,
  type ModelConfigUpdate,
} from '../types/model_config'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'

// ################ 当前用户与权限 ################
const authStore = useAuthStore()
const { isAdmin } = usePermission()

// 响应式: 平板及以上操作列固定右侧
const { isMd } = useResponsive()
const currentUserId = computed(() => authStore.authState.user.id)

/** 是否可管理(编辑/删除)该模型: 全局管理员或创建者本人 */
const canManage = (row: ModelConfig) => isAdmin.value || row.user_id === currentUserId.value

/** 不生效模型整行灰显样式 */
const inactiveRowClass = ({ row }: { row: ModelConfig }) => (row.is_active === false ? 'inactive-row' : '')

// ################ 搜索 ################
// 搜索字段配置(模型标识/类型/方案多字段筛选; 管理员可按所有者用户名过滤)
const searchFields = computed<SearchField[]>(() => {
  const fields: SearchField[] = [
    { prop: 'model', label: '模型标识' },
    {
      prop: 'model_type', label: '模型类型', type: 'select',
      options: modelTypeOptions.map(o => ({ label: o.label, value: o.value as string })),
    },
    {
      prop: 'server_type', label: '服务方案', type: 'select',
      options: [...serverTypeOptionsFor('chat'), ...serverTypeOptionsFor('asr')]
        .map(o => ({ label: o.label, value: o.value as string })),
    },
    {
      prop: 'scope', label: '归属范围', type: 'select',
      options: modelScopeOptions.map(o => ({ label: o.label, value: o.value as string })),
    },
  ]
  // 管理员: 按所有者用户名模糊过滤(查看所有人的模型)
  if (isAdmin.value) {
    fields.push({ prop: 'user', label: '所有者' })
  }
  return fields
})
// 查询参数(与后端列表接口过滤参数对齐)
const queryParams = ref<Record<string, unknown>>({
  model: '',
  model_type: undefined,
  server_type: undefined,
  scope: undefined,
  user: undefined,
})

// ################ 列表 ################
const pagination = ref<PaginationParams>({ page: 1, size: 10 })
const tableData = ref<ModelConfig[]>([])
const total = ref(0)
const loading = ref(false)

/** 获取数据(携带多字段过滤参数) */
const fetchData = async () => {
  try {
    loading.value = true
    const { model, model_type, server_type, scope, user } = queryParams.value
    const response: PaginationResponse<ModelConfig> = await listModelConfigs({
      ...pagination.value,
      model: (model as string) || undefined,
      model_type: (model_type as string) || undefined,
      server_type: (server_type as string) || undefined,
      scope: (scope as string) || undefined,
      user: (user as string) || undefined,
    } as PaginationParams)
    tableData.value = response.items
    total.value = response.total
  }
  catch (error) {
    console.error('获取模型配置列表失败:', error)
    ElMessage.error('获取数据失败，请重试')
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

/** 时间格式化 */
const formatTime = (value: string) =>
  new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })

// ################ 全库重向量化(管理员) ################
const revectorizing = ref(false)
let revTimer: ReturnType<typeof setTimeout> | null = null

/** 轮询任务进度(每2秒, PROGRESS/提交中继续轮询) */
const pollRevectorizeStatus = (taskId: string) => {
  revTimer = setTimeout(async () => {
    try {
      const status = await getRevectorizeStatus(taskId)
      if (status.state === 'PROGRESS' && status.meta) {
        revectorizing.value = true
        ElMessage.info(`重向量化进度: ${status.meta.processed}/${status.meta.total} 文档, 已处理 ${status.meta.chunks} 块`)
        pollRevectorizeStatus(taskId)
      }
      else if (status.state === 'SUCCESS') {
        revectorizing.value = false
        ElMessage.success('全库重向量化完成')
      }
      else if (status.state === 'FAILURE') {
        revectorizing.value = false
        ElMessage.error(`重向量化失败: ${status.error ?? '未知错误'}`)
      }
      else {
        // PENDING/RETRY 等中间状态继续轮询
        pollRevectorizeStatus(taskId)
      }
    }
    catch (error) {
      console.error('查询重向量化进度失败:', error)
      revectorizing.value = false
    }
  }, 2000)
}

/** 提交全库重向量化任务(使用当前生效的默认公共向量化模型) */
const handleRevectorize = () => {
  ElMessageBox.confirm(
    '将以当前生效的默认向量化模型重新计算全部文档向量, 数据量大时耗时较长, 确定执行吗?',
    '重建向量索引',
    { type: 'warning', confirmButtonText: '执行', cancelButtonText: '取消' },
  )
    .then(async () => {
      try {
        revectorizing.value = true
        const res = await revectorizeChunks()
        ElMessage.success(res.message || '任务已提交')
        pollRevectorizeStatus(res.task_id)
      }
      catch (error) {
        console.error('提交重向量化任务失败:', error)
        revectorizing.value = false
        ElMessage.error('任务提交失败')
      }
    })
    .catch(() => {})
}

onBeforeUnmount(() => {
  if (revTimer) clearTimeout(revTimer)
})

// ################ 编辑表单(按类型动态) ################
const dialogVisible = ref(false)
const formRef = ref<FormInstance>()
const submitting = ref(false)
const currentModelConfigId = ref<string | null>(null)

/** 表单数据(extra 以文本形式编辑) */
interface ModelConfigForm {
  model_type: ModelType
  server_type: string
  model: string
  url: string
  api_key: string
  scope: ModelScope
  is_default: boolean
  is_active: boolean
  display_name: string
  pay_in: number
  pay_out: number
  input_tokens: number
  out_tokens: number
  temperature: number
  timeout: number
  no_think: boolean
  extra_text: string
}

const defaultForm = (): ModelConfigForm => ({
  model_type: ModelType.CHAT,
  server_type: 'openai',
  model: '',
  url: '',
  api_key: '',
  scope: ModelScope.USER,
  is_default: false,
  is_active: true,
  display_name: '',
  pay_in: 0,
  pay_out: 0,
  input_tokens: 8192,
  out_tokens: 8192,
  temperature: 0.7,
  timeout: 60,
  no_think: false,
  extra_text: '',
})

const form = reactive<ModelConfigForm>(defaultForm())

/** 归属范围标签样式 */
const scopeTagType: Record<string, 'primary' | 'success' | 'warning' | 'info' | 'danger'> = {
  [ModelScope.PUBLIC]: 'success',
  [ModelScope.DEPT]: 'warning',
  [ModelScope.USER]: 'info',
}

const rules = {
  model: [
    { required: true, message: '请输入模型标识', trigger: 'blur' },
    { min: 1, max: 200, message: '长度在 1 到 200 个字符', trigger: 'blur' },
  ],
}

/** 当前类型是否本地推理(ocr/asr/tts) */
const isLocalType = computed(() =>
  [ModelType.OCR, ModelType.ASR, ModelType.TTS].includes(form.model_type))

/** 当前类型可用方案选项 */
const serverTypeOptions = computed(() => serverTypeOptionsFor(form.model_type))

/** 当前方案 extra 键提示 */
const extraHints = computed(() => extraKeyHints[form.server_type] ?? [])

/** 类型切换: 重置方案为该类型第一个可用项 */
const handleTypeChange = () => {
  const options = serverTypeOptions.value
  if (!options.some(o => o.value === form.server_type)) {
    form.server_type = options[0]?.value ?? ''
  }
}

const dialogTitle = computed(() =>
  currentModelConfigId.value ? '编辑模型配置' : '新增模型配置')

/** 解析 extra 文本为对象(空文本返回 undefined) */
const parseExtra = (): Record<string, unknown> | undefined => {
  const text = form.extra_text.trim()
  if (!text) return undefined
  try {
    const obj = JSON.parse(text)
    if (typeof obj !== 'object' || obj === null || Array.isArray(obj)) {
      throw new Error('必须是 JSON 对象')
    }
    return obj as Record<string, unknown>
  }
  catch (e) {
    throw new Error(`扩展配置 JSON 无效: ${(e as Error).message}`)
  }
}

/** 打开创建对话框 */
const handleCreate = () => {
  Object.assign(form, defaultForm())
  currentModelConfigId.value = null
  dialogVisible.value = true
}

/** 打开编辑对话框(填充详情) */
const handleEdit = async (row: ModelConfig) => {
  try {
    Object.assign(form, defaultForm())
    currentModelConfigId.value = row.id
    const detail = await getModelConfig(row.id)
    form.model_type = detail.model_type
    form.server_type = detail.server_type
    form.model = detail.model || ''
    form.url = detail.url || ''
    form.api_key = detail.api_key || ''
    form.scope = detail.scope ?? ModelScope.USER
    form.is_default = detail.is_default ?? false
    form.is_active = detail.is_active ?? true
    form.display_name = detail.display_name || ''
    form.pay_in = detail.pay_in ?? 0
    form.pay_out = detail.pay_out ?? 0
    form.input_tokens = detail.input_tokens ?? 8192
    form.out_tokens = detail.out_tokens ?? 8192
    form.temperature = detail.temperature ?? 0.7
    form.timeout = detail.timeout ?? 60
    form.no_think = detail.no_think ?? false
    form.extra_text = detail.extra ? JSON.stringify(detail.extra, null, 2) : ''
    dialogVisible.value = true
  }
  catch (error) {
    console.error('获取模型配置详情失败:', error)
    ElMessage.error('获取模型配置详情失败')
  }
}

/** 提交表单(创建或更新) */
const handleSubmit = async () => {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  let extra: Record<string, unknown> | undefined
  try {
    extra = parseExtra()
  }
  catch (e) {
    ElMessage.warning((e as Error).message)
    return
  }

  // 组装载荷(API 类传 url/api_key 等, 本地类不传)
  const isLocal = isLocalType.value
  const payload: ModelConfigCreate | ModelConfigUpdate = {
    model_type: form.model_type,
    server_type: form.server_type as ModelConfigCreate['server_type'],
    model: form.model,
    scope: form.scope,
    is_default: form.scope === ModelScope.PUBLIC ? form.is_default : false,
    // 仅管理员可切换生效状态(非管理员不传, 保持原值)
    is_active: isAdmin.value ? form.is_active : undefined,
    display_name: form.display_name.trim() || undefined,
    url: isLocal ? undefined : (form.url || undefined),
    api_key: isLocal ? undefined : (form.api_key || undefined),
    timeout: isLocal ? undefined : (form.timeout || undefined),
    pay_in: isLocal ? undefined : (form.pay_in ?? 0),
    pay_out: isLocal ? undefined : (form.pay_out ?? 0),
    input_tokens: form.model_type === ModelType.CHAT ? form.input_tokens : undefined,
    out_tokens: [ModelType.CHAT, ModelType.EMBEDDINGS].includes(form.model_type)
      ? form.out_tokens
      : undefined,
    temperature: form.model_type === ModelType.CHAT ? form.temperature : undefined,
    no_think: form.model_type === ModelType.CHAT ? form.no_think : undefined,
    extra,
  }

  try {
    submitting.value = true
    if (currentModelConfigId.value) {
      await updateModelConfig(currentModelConfigId.value, payload as ModelConfigUpdate)
      ElMessage.success('更新成功')
    }
    else {
      await createModelConfig(payload as ModelConfigCreate)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await fetchData()
  }
  catch (error) {
    console.error('保存模型配置失败:', error)
    ElMessage.error('保存失败, 请重试')
  }
  finally {
    submitting.value = false
  }
}

/** 删除模型配置 */
const handleDelete = (row: ModelConfig) => {
  ElMessageBox.confirm(
    `确定删除模型「${row.model}」的配置吗?`,
    '删除确认',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  )
    .then(async () => {
      try {
        await deleteModelConfig(row.id)
        ElMessage.success('删除成功')
        if (tableData.value.length === 1 && pagination.value.page > 1) {
          pagination.value.page -= 1
        }
        await fetchData()
      }
      catch (error) {
        console.error('删除模型配置失败:', error)
        ElMessage.error('删除失败')
      }
    })
    .catch(() => {})
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
/* 不生效(灰色)模型行: 整行弱化显示 */
:deep(.el-table .inactive-row) {
  opacity: 0.55;
}
:deep(.el-table .inactive-row td) {
  color: var(--el-text-color-secondary);
}
</style>
