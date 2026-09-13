<template>
  <!-- 结构体智能体运行面板(内嵌对话页: 配置了 JSON 输入/输出的智能体在此执行) -->
  <div class="flex-1 min-h-0 overflow-y-auto w-full">
    <div class="max-w-3xl mx-auto px-4 py-5 flex flex-col gap-4">
      <!-- 头部: 智能体信息 + 结构标签 -->
      <div class="flex items-start gap-3">
        <div class="w-10 h-10 rounded-xl bg-note-tint flex-center shrink-0">
          <el-icon :size="20" text-note-green><MagicStick /></el-icon>
        </div>
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="font-bold text-note">{{ agent.name }}</span>
            <el-tag size="small" effect="plain" :type="agent.input_type === 'json' ? 'warning' : 'info'">
              输入: {{ agent.input_type === 'json' ? 'JSON 结构体' : '字符串' }}
            </el-tag>
            <el-tag size="small" effect="plain" :type="agent.output_type === 'json' ? 'warning' : 'info'">
              输出: {{ agent.output_type === 'json' ? 'JSON 结构体' : '字符串' }}
            </el-tag>
          </div>
          <p class="text-xs text-note-sub mt-1 m-0">{{ agent.description || '该智能体配置了结构体, 通过下方表单运行' }}</p>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="p-4 rounded-2xl bg-note-card shadow-note flex flex-col gap-3">
        <div class="flex flex-wrap items-center gap-2">
          <LLMSelect v-model:model-id="modelId" :model-list="models" :disabled="isRunning" />
          <span class="flex-1" />
          <el-button
            type="success" :loading="isRunning"
            :disabled="!modelId || !inputText.trim() || isRunning"
            @click="handleRun"
          >
            <el-icon v-if="!isRunning" class="mr-1"><VideoPlay /></el-icon>
            {{ isRunning ? '运行中...' : '运行' }}
          </el-button>
        </div>

        <div>
          <div class="flex items-center justify-between mb-1">
            <span class="text-sm font-medium text-note">输入</span>
            <span v-if="agent.input_type === 'json'" class="text-xs text-note-sub">
              按输入结构填写 JSON{{ agent.input_schema ? '(见下方结构说明)' : '' }}
            </span>
          </div>
          <!-- JSON 输入: Monaco 编辑 -->
          <div v-if="agent.input_type === 'json'" class="h-48 rounded-lg overflow-hidden border border-note">
            <LazyMonacoJson v-model="inputText" language="json" class="h-full" />
          </div>
          <!-- 字符串输入 -->
          <el-input
            v-else v-model="inputText" type="textarea" :rows="6"
            placeholder="请输入要处理的内容"
          />
        </div>

        <!-- 输入结构说明(JSON Schema) -->
        <el-collapse v-if="agent.input_schema" class="border-none">
          <el-collapse-item title="输入结构说明(JSON Schema)" name="input-schema">
            <pre class="text-xs text-note-sub whitespace-pre-wrap m-0 bg-note-soft rounded-lg p-2.5">{{ inputSchemaText }}</pre>
          </el-collapse-item>
        </el-collapse>
      </div>

      <!-- 结果区 -->
      <div v-if="result !== null" class="p-4 rounded-2xl bg-note-card shadow-note">
        <div class="flex items-center justify-between mb-2">
          <span class="text-sm font-bold text-note">运行结果</span>
          <el-tag v-if="viewingRecordId" size="small" type="info" effect="plain" closable @close="resetToNew">
            历史回看
          </el-tag>
        </div>
        <pre class="text-sm whitespace-pre-wrap m-0 text-note bg-note-soft rounded-lg p-3 overflow-x-auto">{{ resultText }}</pre>

        <!-- 工作流节点执行轨迹(仅工作流智能体返回) -->
        <div v-if="trace.length > 0" class="mt-3">
          <el-collapse class="border-none">
            <el-collapse-item name="trace">
              <template #title>
                <span class="text-sm font-medium text-note">节点执行轨迹({{ trace.length }})</span>
              </template>
              <div class="flex flex-col gap-1">
                <div
                  v-for="t in trace" :key="t.node_id"
                  class="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-note-soft/70 text-xs"
                >
                  <span
                    class="w-2 h-2 rounded-full shrink-0"
                    :class="t.status === 'success' ? 'bg-green-500' : t.status === 'failed' ? 'bg-red-500' : 'bg-gray-300'"
                  />
                  <span class="font-medium text-note">{{ t.node_type }}</span>
                  <span class="text-note-sub font-mono">{{ t.node_id }}</span>
                  <span class="text-note-sub">{{ t.duration_ms }}ms</span>
                  <span class="flex-1" />
                  <el-popover trigger="click" width="320">
                    <template #reference>
                      <button type="button" class="text-note-sub hover:text-note-green transition-colors">
                        查看输出
                      </button>
                    </template>
                    <pre class="text-xs whitespace-pre-wrap m-0 max-h-60 overflow-auto">{{ traceDetail(t) }}</pre>
                  </el-popover>
                </div>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>
      </div>

      <!-- 空结果占位 -->
      <div v-else class="py-8 flex flex-col items-center text-note-sub">
        <el-icon text-4xl mb-2 class="opacity-40"><VideoPlay /></el-icon>
        <p class="text-sm m-0">选择模型并填入输入, 点击"运行"查看结果</p>
      </div>

      <!-- 运行历史 -->
      <div class="p-4 rounded-2xl bg-note-card shadow-note">
        <div class="flex items-center justify-between mb-2">
          <span class="text-sm font-bold text-note">运行历史</span>
          <el-button size="small" text bg :loading="historyLoading" @click="loadHistory">刷新</el-button>
        </div>
        <div v-if="history.length > 0" class="flex flex-col gap-1.5">
          <button
            v-for="record in history" :key="record.id"
            class="flex items-center gap-2 px-3 py-2 rounded-lg text-left transition-colors"
            :class="viewingRecordId === record.id ? 'bg-note-tint' : 'hover:bg-note-tint/60'"
            @click="viewRecord(record)"
          >
            <el-icon :size="14" class="shrink-0 opacity-60 text-note-sub"><Clock /></el-icon>
            <span class="text-xs text-note-sub shrink-0">{{ formatTime(record.created_at) }}</span>
            <span class="text-xs text-note-sub truncate flex-1">{{ previewInput(record.input) }}</span>
            <el-tag size="small" effect="plain" type="info">
              {{ typeof record.output === 'string' ? '文本' : 'JSON' }}
            </el-tag>
          </button>
        </div>
        <div v-else class="py-4 text-center text-xs text-note-sub">暂无运行记录</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// 智能体运行面板: 原 data_clean 能力并入(结构体配置驱动的一次性运行 + 历史回看)
import { ElMessage } from 'element-plus'
import { MagicStick, VideoPlay, Clock } from '@element-plus/icons-vue'
import type { PaginationParams, PaginationResponse } from '@/common/types/common'
import type { ModelConfig } from '../../ai/types/model_config'
import { listModelConfigs } from '../../ai/api/model_config'
import LLMSelect from '../../ai/components/LLMSelect.vue'
import { runAgent, listAgentRuns } from '../api/agent'
import type { Agent, AgentRunRecord, NodeTrace } from '../types'

const props = defineProps<{
  /** 当前选中的智能体(已配置结构体) */
  agent: Agent
}>()

// Monaco 异步加载(重库独立 chunk)
const LazyMonacoJson = defineAsyncComponent(
  () => import('@/common/components/ide/BaseMoacoEdit.vue'),
)

// ===== 模型(复用 AI 模块模型配置) =====
const models = ref<ModelConfig[]>([])
const modelId = ref('')

const loadModels = async () => {
  try {
    const params = { page: 1, size: 50, model_type: 'chat' } as PaginationParams
    const res: PaginationResponse<ModelConfig> = await listModelConfigs(params)
    models.value = res.items
    if (res.items.length > 0) modelId.value = res.items[0].id
  } catch (error) {
    console.error('加载模型列表失败:', error)
    ElMessage.error('加载模型列表失败')
  }
}

// ===== 运行状态 =====
const inputText = ref('')
const isRunning = ref(false)
const result = ref<unknown>(null)
const viewingRecordId = ref<string | null>(null)
// 工作流节点执行轨迹(仅工作流智能体返回)
const trace = ref<NodeTrace[]>([])

const inputSchemaText = computed(() =>
  props.agent.input_schema ? JSON.stringify(props.agent.input_schema, null, 2) : '',
)

const resultText = computed(() =>
  typeof result.value === 'string' ? result.value : JSON.stringify(result.value, null, 2),
)

// 执行运行(JSON 输入先解析校验)
const handleRun = async () => {
  if (isRunning.value || !modelId.value || !inputText.value.trim()) return

  let input: unknown = inputText.value
  if (props.agent.input_type === 'json') {
    try {
      input = JSON.parse(inputText.value)
    } catch {
      ElMessage.warning('输入 JSON 格式不正确, 请检查后重试')
      return
    }
  }

  isRunning.value = true
  try {
    const res = await runAgent(props.agent.id, { model_id: modelId.value, input })
    result.value = res.result
    trace.value = res.trace ?? []
    viewingRecordId.value = res.run_id
    loadHistory()
  } catch (error) {
    console.error('智能体运行失败:', error)
    ElMessage.error('运行失败: ' + (error instanceof Error ? error.message : '未知错误'))
  } finally {
    isRunning.value = false
  }
}

// ===== 运行历史 =====
const history = ref<AgentRunRecord[]>([])
const historyLoading = ref(false)

const loadHistory = async () => {
  historyLoading.value = true
  try {
    const res = await listAgentRuns(props.agent.id, { page: 1, size: 20 })
    history.value = res.items
  } catch (error) {
    console.error('加载运行历史失败:', error)
  } finally {
    historyLoading.value = false
  }
}

// 回看历史记录(输入/结果/轨迹填充为该次运行)
const viewRecord = (record: AgentRunRecord) => {
  viewingRecordId.value = record.id
  result.value = record.output
  trace.value = record.trace?.nodes ?? []
  inputText.value =
    typeof record.input === 'string' ? record.input : JSON.stringify(record.input, null, 2)
}

// 清除回看, 回到新运行状态
const resetToNew = () => {
  viewingRecordId.value = null
  result.value = null
  trace.value = []
}

// 轨迹详情文本(状态/错误/输出)
const traceDetail = (t: NodeTrace) => {
  const parts = [`状态: ${t.status}`]
  if (t.error) parts.push(`错误: ${t.error}`)
  parts.push(`输出: ${typeof t.output === 'string' ? t.output : JSON.stringify(t.output, null, 2)}`)
  return parts.join('\n')
}

const formatTime = (value: string) => new Date(value).toLocaleString()

const previewInput = (input: unknown) => {
  const text = typeof input === 'string' ? input : JSON.stringify(input)
  return text.length > 60 ? `${text.slice(0, 60)}...` : text
}

// 切换智能体时重置面板
watch(
  () => props.agent.id,
  () => {
    inputText.value = ''
    result.value = null
    viewingRecordId.value = null
    trace.value = []
    history.value = []
    loadHistory()
  },
  { immediate: true },
)

onMounted(() => {
  loadModels()
})
</script>
