<template>
  <div p-4 max-w-6xl mx-auto>
    <h1 text-center mb-5 text-2xl font-bold>LLM 数据清洗</h1>

    <!-- 参数配置区域 -->
    <el-card mb-5>
      <div flex flex-col gap-4>
        <!-- 模型选择 -->
        <div flex flex-wrap items-center gap-3>
          <LLMSelect v-model:model-id="model_id" :model-list="tableData" :disabled="isCleaning" />
          <el-button
            type="success"
            :loading="isCleaning"
            :disabled="!model_id || !dataText.trim() || isCleaning"
            @click="startClean"
          >
            {{ isCleaning ? '清洗中...' : '开始清洗' }}
          </el-button>
        </div>

        <!-- 待清洗数据 -->
        <div>
          <div flex items-center justify-between mb-1>
            <span text-sm font-medium>待清洗数据</span>
            <span text-xs text-note-sub>支持 JSON 对象/数组或纯字符串</span>
          </div>
          <el-input
            v-model="dataText"
            type="textarea"
            :rows="8"
            placeholder='请输入 JSON 或字符串, 例如: {"name":"张三 ","age":"28","phone":"138-0013-8000"}'
          />
        </div>

        <!-- 清洗提示词 -->
        <div>
          <div mb-1>
            <span text-sm font-medium>清洗提示词</span>
          </div>
          <el-input
            v-model="prompt"
            type="textarea"
            :rows="3"
            placeholder="例如: 去除所有字段首尾空格, 手机号统一脱敏为 138****8000 格式, 年龄转数字"
          />
        </div>

        <!-- 输出类型 -->
        <div flex flex-wrap items-center gap-3>
          <span text-sm font-medium>输出类型:</span>
          <el-radio-group v-model="output_type">
            <el-radio value="json" border>JSON(结构化)</el-radio>
            <el-radio value="string" border>字符串</el-radio>
          </el-radio-group>
        </div>

        <!-- JSON Schema(输出类型为 json 时) -->
        <div v-if="output_type === 'json'">
          <div flex items-center justify-between mb-1>
            <span text-sm font-medium>JSON 结构(Schema)</span>
            <span text-xs text-note-sub>可选; 提供后模型将严格按该结构输出</span>
          </div>
          <el-input
            v-model="schemaText"
            type="textarea"
            :rows="6"
            placeholder='例如: {"type":"object","properties":{"name":{"type":"string"},"age":{"type":"integer"},"phone":{"type":"string"}},"required":["name","age","phone"]}'
          />
        </div>
      </div>
    </el-card>

    <!-- 结果展示 -->
    <el-card v-if="result !== null">
      <div font-bold mb-3>清 洗 结 果</div>
      <div border rounded p-3 bg-gray-50>
        <pre v-if="output_type === 'json'" text-sm whitespace-pre-wrap m-0>{{ resultText }}</pre>
        <div v-else text-sm whitespace-pre-wrap>{{ resultText }}</div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import type { PaginationParams, PaginationResponse } from '@/common/types/common'
import type { ModelConfig } from '../types/model_config'
import type { DataCleanOutputType } from '../types/data_clean'
import { listModelConfigs } from '../api/model_config'
import { cleanData } from '../api/data_clean'
import LLMSelect from '../components/LLMSelect.vue'

// ===== 模型配置 =====
const pagination = ref<PaginationParams>({ page: 1, size: 50 })
const model_id = ref('')
const tableData = ref<ModelConfig[]>([])

// ===== 清洗参数 =====
const dataText = ref('')
const prompt = ref('')
const output_type = ref<DataCleanOutputType>('json')
const schemaText = ref('')

// ===== 清洗状态 =====
const isCleaning = ref(false)
const result = ref<unknown>(null)
const resultText = ref('')

// 加载模型配置列表(仅对话类模型, 默认选中第一个)
onMounted(async () => {
  try {
    const response: PaginationResponse<ModelConfig> = await listModelConfigs({
      ...pagination.value,
      model_type: 'chat',
    } as PaginationParams)
    tableData.value = response.items
    if (response.items.length > 0) {
      model_id.value = response.items[0].id
    }
  } catch (error) {
    console.error('加载模型列表失败:', error)
    ElMessage.error('加载模型列表失败')
  }
})

// 开始清洗
const startClean = async () => {
  if (!dataText.value.trim() || !model_id.value || isCleaning.value) return

  // 输入数据: 优先解析为 JSON, 解析失败按字符串处理
  let parsedData: unknown = dataText.value
  try {
    parsedData = JSON.parse(dataText.value)
  } catch {
    parsedData = dataText.value
  }

  // JSON Schema: 仅输出类型为 json 且填写时解析, 解析失败不限制结构
  let jsonSchema: Record<string, unknown> | undefined
  if (output_type.value === 'json' && schemaText.value.trim()) {
    try {
      jsonSchema = JSON.parse(schemaText.value)
    } catch {
      ElMessage.warning('JSON Schema 格式不正确, 将不限制输出结构')
    }
  }

  isCleaning.value = true
  result.value = null
  resultText.value = ''
  try {
    const res = await cleanData({
      model_id: model_id.value,
      data: parsedData,
      prompt: prompt.value,
      output_type: output_type.value,
      json_schema: jsonSchema,
    })
    result.value = res.result
    resultText.value =
      typeof res.result === 'string' ? res.result : JSON.stringify(res.result, null, 2)
  } catch (error) {
    console.error('数据清洗失败:', error)
    ElMessage.error('数据清洗失败: ' + (error instanceof Error ? error.message : '未知错误'))
  } finally {
    isCleaning.value = false
  }
}
</script>
