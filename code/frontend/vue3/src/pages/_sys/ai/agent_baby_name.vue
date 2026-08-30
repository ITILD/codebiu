<template>
  <div flex flex-col h-app w-full bg-gray-50>
    <!-- 顶部模型选择栏 -->
    <div p-4 border-b bg-white shadow-sm>
      <div flex flex-wrap items-center gap-4>
        <LLMSelect v-model:model-id="model_id" :model-list="tableData" :disabled="isSending"
          @change="handleModelChange" />
      </div>
    </div>

    <!-- 主体内容区 -->
    <div flex flex-1 flex-col md:flex-row overflow-hidden>
      <!-- 左侧表单输入区 -->
      <div w-full md:w-100 border-r bg-white p-4 overflow-y-auto>
        <div text-lg font-bold mb-4>宝宝信息</div>

        <el-form :model="formData" label-width="80px" size="small">
          <el-form-item label="姓氏" required>
            <el-input v-model="formData.surname" placeholder="请输入姓氏" :disabled="isSending" />
          </el-form-item>

          <el-form-item label="性别" required>
            <el-radio-group v-model="formData.gender" :disabled="isSending">
              <el-radio value="boy">男宝</el-radio>
              <el-radio value="girl">女宝</el-radio>
              <el-radio value="unknown">未知</el-radio>
            </el-radio-group>
          </el-form-item>

          <el-form-item label="出生日期" required>
            <el-date-picker v-model="formData.birth_date" type="date" placeholder="选择出生日期" format="YYYY-MM-DD"
              value-format="YYYY-MM-DD" :disabled="isSending" w-full />
          </el-form-item>

          <el-form-item label="出生时辰" required>
            <el-time-picker v-model="formData.birth_time" placeholder="选择出生时辰" format="HH:mm" value-format="HH:mm"
              :disabled="isSending" w-full />
          </el-form-item>

          <el-form-item label="名字长度">
            <el-input-number v-model="formData.name_length" :min="1" :max="5" :step="1" :disabled="isSending"
              w-full />
          </el-form-item>

          <el-form-item label="其他要求">
            <el-input v-model="formData.other" type="textarea" :rows="4" placeholder="如：避免使用某些字、偏好某种风格、特殊含义等"
              :disabled="isSending" />
          </el-form-item>

          <el-button type="primary" :loading="isSending" :disabled="!canSubmit" @click="handlePredict"
            w-full>
            {{ isSending ? '预测中...' : '开始预测' }}
          </el-button>
        </el-form>
      </div>

      <!-- 右侧结果显示区 -->
      <div flex-1 flex flex-col overflow-hidden>
        <!-- 结果列表 -->
        <div flex-1 overflow-y-auto p-4>
          <div v-if="!result.explanation_constellation && !result.explanation_wuxing" flex flex-col items-center
            justify-center h-full text-gray-400>
            <div text-6xl mb-4>👶</div>
            <div text-lg>等待预测</div>
            <div text-sm>填写左侧宝宝信息后点击预测</div>
          </div>

          <div v-else>
            <div mb-4 flex justify-between items-center>
              <div text-lg font-bold>预测结果</div>
              <el-button size="small" @click="clearResults">清空结果</el-button>
            </div>

            <div grid grid-cols-1 gap-4>


              <div space-y-3>
                <div>
                  <div text-sm font-semibold text-gray-700 mb-1>五行解释</div>
                  <div text-sm text-gray-600 leading-relaxed
                    v-html="renderMarkdown(result.explanation_wuxing || '正在生成......')"></div>
                </div>

                <div>
                  <div text-sm font-semibold text-gray-700 mb-1>星座解释</div>
                  <div text-sm text-gray-600 leading-relaxed
                    v-html="renderMarkdown(result.explanation_constellation || '正在生成......')"></div>
                </div>

                <div>
                  <div text-sm font-semibold text-gray-700 mb-1>名字及解释</div>
                  <div text-sm text-gray-600 leading-relaxed
                    v-html="renderMarkdown(result.explanation_meaning_list || '正在生成......')"></div>
                </div>
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  type PaginationParams,
  type PaginationResponse,
} from '@/types/common';
import type { ModelConfig } from '@/types/model_config';
import { listModelConfigs } from '@/api/model_config'
import { predictBabyNameStream } from '@/api/life/baby_name'
import type {
  NameInfoPredictFullRequest,
  NameInfoResponse,
  GenderEnum
} from '@/types/life/baby_name'
import LLMSelect from '@/components/app/ai/LLMSelect.vue'
import { marked } from 'marked'

// 渲染 Markdown 内容
const renderMarkdown = (content: string) => {
  return marked.parse(content)
}

// 分页参数
const pagination = ref<PaginationParams>({
  page: 1,
  size: 10
})

const model_id = ref('')

// 表格数据
const tableData = ref<ModelConfig[]>([])

// 表单数据
const formData = ref<NameInfoPredictFullRequest>({
  surname: '',
  gender: 'unknown' as GenderEnum,
  birth_date: '',
  birth_time: '',
  name_length: 2,
  other: '',
  model_id: ''
})

// 结果列表
const result = ref<NameInfoResponse>(
  {
    explanation_wuxing: '',
    explanation_constellation: '',
    explanation_meaning_list: ''
  }
)

// 发送状态
const isSending = ref(false)

// 是否可以提交
const canSubmit = computed(() => {
  return formData.value.surname &&
    formData.value.gender &&
    formData.value.birth_date &&
    formData.value.birth_time &&
    model_id.value
})



// 清空结果
const clearResults = () => {
  result.value.explanation_constellation = ''
  result.value.explanation_meaning_list = ''
  result.value.explanation_wuxing = ''
}

// 处理模型变化
const handleModelChange = (modelId: string) => {
  console.log('模型已切换至:', modelId)
}

// 开始预测
const handlePredict = async () => {
  if (!canSubmit.value || isSending.value) {
    return
  }

  // 清空之前的结果
  clearResults()

  // 设置发送状态
  isSending.value = true

  try {
    // 调用流式预测接口
    await predictBabyNameStream(
      {
        ...formData.value,
        model_id: model_id.value
      },
      // 接收数据块回调（立即更新）
      (result_obj: any) => {
        // 添加结果
        if (result_obj.node_name == "calculate_constellation_preference") {
          result.value.explanation_constellation += result_obj.content
        }
        if (result_obj.node_name == "calculate_wuxing_preference") {
          result.value.explanation_wuxing += result_obj.content
        }
        if (result_obj.node_name == "generate_name_result") {
          result.value.explanation_meaning_list += result_obj.content
        }
      },
      // 错误回调
      (error: string) => {
        ElMessage.error(`预测失败：${error}`)
        isSending.value = false
      },
      // 完成回调
      () => {
        isSending.value = false
        ElMessage.success('预测完成')
      }
    )
  } catch (error) {
    console.error('预测失败:', error)
    ElMessage.error('预测失败，请重试')
    isSending.value = false
  }
}

// 初始化
onMounted(async () => {
  // 获取模型配置列表
  const params = {
    ...pagination.value,
  }

  const response: PaginationResponse<ModelConfig> = await listModelConfigs(params)
  tableData.value = response.items
  if (response.items.length > 0) {
    model_id.value = response.items[0].id
  }
})
</script>
