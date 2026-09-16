<template>
  <div class="max-w-[640px]" flex flex-col gap-5>
    <div>
      <h3 text-lg font-medium text-note m-0>模型设置</h3>
      <p text-sm text-note-sub mt-1 mb-0>
        为对话/向量化/重排及语音类(识别/合成/VAD/降噪)选择个人默认模型(可选用公共/本部门/自己的模型);
        未选择时自动跟随系统默认公共模型(下拉回显其模型名)
      </p>
    </div>

    <el-form v-loading="loading" label-width="96px" label-position="right" flex flex-col gap-1>
      <el-form-item v-for="meta in TYPE_META" :key="meta.type" :label="meta.label">
        <!-- 同一行布局: 左侧模型选择器 + 右侧测试按钮(仅测试当前选中模型) -->
        <div class="w-full flex items-center gap-2">
          <el-select :model-value="displayValue(meta.type)"
            placeholder="未绑定(自动使用系统默认模型)"
            clearable class="flex-1 min-w-0" @update:model-value="(v) => handleSelect(meta.type, v)">
            <!-- 选中态自定义展示: 模型名 + 系统默认tag + 已测能力标签(测试后显示当前支持的能力) -->
            <template #label="{ value }">
              <span flex items-center gap-1>
                <span>{{ selectedText(meta.type, value) }}</span>
                <el-tag v-if="selectedIsDefault(meta.type, value)" type="warning" size="small">默认</el-tag>
                <el-tooltip v-for="cap in selectedCapabilities(meta.type)" :key="cap.key"
                  :content="cap.ok ? (cap.detail || '测试通过') : (cap.error || '测试未通过')" placement="top">
                  <el-tag :type="cap.ok ? 'success' : 'danger'" size="small"
                    effect="light">
                    {{ cap.label }}
                  </el-tag>
                </el-tooltip>
              </span>
            </template>
            <el-option v-for="item in modelMap[meta.type]" :key="item.id" :value="item.id"
              :label="modelMainLabel(item)" :disabled="item.is_active === false">
              <!-- 选项首行: 模型名 + 标记 + 已测能力标签(通过=绿/失败=红, 仅颜色区分) -->
              <div flex flex-col>
                <div flex items-center gap-1>
                  <span>{{ modelMainLabel(item) }}</span>
                  <el-tag v-if="item.is_default" type="warning" size="small">默认</el-tag>
                  <el-tag v-if="item.is_active === false" type="info" size="small">不生效</el-tag>
                  <el-tooltip v-for="cap in testedCapabilities(item)" :key="cap.key"
                    :content="cap.ok ? (cap.detail || '测试通过') : (cap.error || '测试未通过')" placement="top">
                    <el-tag :type="cap.ok ? 'success' : 'danger'" size="small"
                      effect="light">
                      {{ cap.label }}
                    </el-tag>
                  </el-tooltip>
                </div>
                <div text-xs text-note-sub>
                  {{ item.model }} · {{ serverTypeLabel(item.server_type) }} · {{ scopeShortLabel(item.scope) }}
                </div>
              </div>
            </el-option>
          </el-select>
          <!-- 测试当前选中模型 -->
          <el-button class="shrink-0" :disabled="!selectedModel(meta.type)"
            :loading="isTestingSelected(meta.type)" @click="handleTestSelected(meta.type)">
            测试
          </el-button>
        </div>
      </el-form-item>

      <el-form-item>
        <el-button class="px-6" type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup lang="ts">
// 设置页-模型设置面板: 用户级模型绑定/切换(未绑定的类型默认使用系统默认公共模型)
// 覆盖 7 类模型: 对话/向量化/重排 + 语音识别/合成/VAD断句/降噪(语音服务按用户绑定解析引擎)
// 模型配置的管理(新增/统计/默认公共模型配置)在 /ai/model_config 页, 仅系统管理员与授权人员使用
import { listModelConfigs, testModelCapability } from '@/modules/ai/api/model_config'
import {
  modelMainLabel,
  scopeShortLabel,
  serverTypeLabel,
  testedCapabilities,
} from '@/modules/ai/types/model_config'
import type { ModelConfig, ModelCapabilityResult } from '@/modules/ai/types/model_config'
import { getMyModelBinding, updateMyModelBinding } from '@/modules/rag/api/user_model'
import type { UserModelBindingUpdate } from '@/modules/rag/api/user_model'
import { ElMessage } from 'element-plus'
import type { PaginationParams } from '@/common/types/common'

// 可绑定的模型类型(与后端 ModelType 值对齐; 全部类型支持能力测试)
type BindableType = 'chat' | 'embeddings' | 'rerank' | 'asr' | 'tts' | 'vad' | 'denoise'

/** 绑定面板元信息(未绑定时均自动回落系统默认模型) */
const TYPE_META: { type: BindableType; label: string }[] = [
  { type: 'chat', label: '对话模型' },
  { type: 'embeddings', label: '向量化模型' },
  { type: 'rerank', label: '重排模型' },
  { type: 'asr', label: '语音识别(ASR)' },
  { type: 'tts', label: '语音合成(TTS)' },
  { type: 'vad', label: 'VAD断句' },
  { type: 'denoise', label: '降噪' },
]
const BINDABLE_TYPES = TYPE_META.map(m => m.type)

/** 模型类型 -> 绑定字段名常量表 */
const BINDING_KEYS = {
  chat: 'chat_model_id',
  embeddings: 'embedding_model_id',
  rerank: 'rerank_model_id',
  asr: 'asr_model_id',
  tts: 'tts_model_id',
  vad: 'vad_model_id',
  denoise: 'denoise_model_id',
} as const
type BindingKey = (typeof BINDING_KEYS)[BindableType]

const loading = ref(false)
const saving = ref(false)

// 绑定表单(模型ID, null=未绑定→自动使用系统默认公共模型)
const binding = reactive<Record<BindingKey, string | null>>({
  chat_model_id: null,
  embedding_model_id: null,
  rerank_model_id: null,
  asr_model_id: null,
  tts_model_id: null,
  vad_model_id: null,
  denoise_model_id: null,
})

// 各类型可见模型列表(公共/本部门/本人, 后端按当前用户过滤)
const modelMap = reactive<Record<BindableType, ModelConfig[]>>({
  chat: [],
  embeddings: [],
  rerank: [],
  asr: [],
  tts: [],
  vad: [],
  denoise: [],
})

/** 查找某类型当前生效的系统默认公共模型ID(未找到返回 null) */
const defaultModelId = (type: BindableType) =>
  modelMap[type].find(
    (m) => m.is_default && m.is_active !== false && m.scope === 'public'
  )?.id ?? null

/** 选中态展示文案(#label 插槽用): 按类型+模型ID反查配置取主文案 */
const selectedText = (type: BindableType, value: unknown) => {
  const item = modelMap[type].find((m) => m.id === value)
  return item ? modelMainLabel(item) : ''
}

/** 选中项是否为系统默认公共模型(#label 插槽用) */
const selectedIsDefault = (type: BindableType, value: unknown) =>
  modelMap[type].some((m) => m.id === value && m.is_default)

/** 当前展示的模型ID: 未绑定(null)时回显系统默认公共模型(与后端实际生效一致) */
const displayValue = (type: BindableType) => binding[BINDING_KEYS[type]] ?? defaultModelId(type)

/** 下拉选择: 选中默认公共模型/清除 均归一化为 null(跟随默认, 管理员更换默认后无缝切换) */
const handleSelect = (type: BindableType, v: unknown) => {
  binding[BINDING_KEYS[type]] = v && v !== defaultModelId(type) ? (v as string) : null
}

/** 当前生效的模型配置对象(按类型, 未绑定时即默认公共模型) */
const selectedModel = (type: BindableType): ModelConfig | undefined =>
  modelMap[type].find((m) => m.id === displayValue(type))

/** 当前选中模型已测能力(#label 插槽: 测试后显示当前支持的能力) */
const selectedCapabilities = (type: BindableType) => testedCapabilities(selectedModel(type))

// ################ 能力测试 ################
// 正在测试的模型配置ID(右侧测试按钮共用同一 loading 态)
const testingId = ref<string | null>(null)

/** 当前选中模型是否正在测试(右侧测试按钮 loading 态) */
const isTestingSelected = (type: BindableType) => {
  const item = selectedModel(type)
  return !!item && testingId.value === item.id
}

/** 运行指定模型的能力测试(含语音类模拟音频冒烟), 结果持久化到后端并展示为能力标签 */
const handleTestModel = async (item: ModelConfig) => {
  try {
    testingId.value = item.id
    const res = await testModelCapability(item.id)
    // 合并测试结果到本地模型数据(后端 check_result 已同步持久化)
    const merged: Record<string, ModelCapabilityResult> = { ...(item.check_result ?? {}) }
    for (const cap of res.capabilities) merged[cap.capability] = { ...cap, checked_at: res.checked_at }
    item.check_result = merged
    const passed = res.capabilities.filter((c) => c.ok).length
    if (passed === res.capabilities.length) ElMessage.success(`测试完成: ${passed}/${res.capabilities.length} 项能力通过`)
    else ElMessage.warning(`测试完成: ${passed}/${res.capabilities.length} 项能力通过, 失败项见红色标签`)
  } catch (error) {
    console.error('模型能力测试失败:', error)
    ElMessage.error('模型能力测试失败')
  } finally {
    testingId.value = null
  }
}

/** 运行当前选中模型的能力测试(选择器右侧按钮) */
const handleTestSelected = (type: BindableType) => {
  const item = selectedModel(type)
  if (item) handleTestModel(item)
}

/** 拉取单个类型的可见模型列表 */
const fetchModels = async (type: BindableType) => {
  try {
    const res = await listModelConfigs({ page: 1, size: 200, model_type: type } as PaginationParams)
    modelMap[type] = res.items
  } catch (error) {
    console.error(`获取${type}模型列表失败:`, error)
  }
}

/** 初始化: 并行拉取绑定 + 各类型模型列表(存储保持 null=跟随默认, 展示层负责回显默认公共模型) */
const init = async () => {
  loading.value = true
  try {
    const [bind] = await Promise.all([
      getMyModelBinding(),
      ...BINDABLE_TYPES.map((t) => fetchModels(t)),
    ])
    const data = bind as unknown as Record<string, string | null>
    for (const { type } of TYPE_META) {
      binding[BINDING_KEYS[type]] = data[BINDING_KEYS[type]] ?? null
    }
  } catch (error) {
    console.error('获取模型绑定失败:', error)
    ElMessage.error('获取模型绑定失败')
  } finally {
    loading.value = false
  }
}

/** 保存绑定(绑定前校验由后端完成: 公共/本部门/本人模型才允许绑定);
 *  fallback_disabled 固定传 false: 回退开关已移除, 顺带清理历史遗留的关闭回退标记 */
const handleSave = async () => {
  try {
    saving.value = true
    const payload: Record<string, string | null | boolean> = { fallback_disabled: false }
    for (const { type } of TYPE_META) payload[BINDING_KEYS[type]] = binding[BINDING_KEYS[type]]
    await updateMyModelBinding(payload as UserModelBindingUpdate)
    ElMessage.success('模型设置已保存')
  } catch (error) {
    console.error('保存模型设置失败:', error)
    ElMessage.error('保存失败(仅可绑定公共/本部门/自己的模型)')
  } finally {
    saving.value = false
  }
}

onMounted(init)
</script>
