<template>
  <div class="max-w-[640px]" flex flex-col gap-5>
    <div>
      <h3 text-lg font-medium text-note m-0>模型设置</h3>
      <p text-sm text-note-sub mt-1 mb-0>
        为对话/向量化/重排选择个人默认模型(可选用公共/本部门/自己的模型); 未选择时自动跟随系统默认公共模型(下拉回显其模型名)
      </p>
    </div>

    <el-form v-loading="loading" label-width="96px" label-position="right" flex flex-col gap-1>
      <!-- 对话模型绑定 -->
      <el-form-item label="对话模型">
        <div class="w-full flex flex-col gap-1">
          <el-select v-model="displayChat" placeholder="暂无系统默认公共模型, 请联系管理员配置" clearable w-full>
            <!-- 选中态自定义展示: 模型名 + 系统默认tag(与下拉选项一致) -->
            <template #label="{ value }">
              <span flex items-center gap-1>
                <span>{{ selectedText('chat', value) }}</span>
                <el-tag v-if="selectedIsDefault('chat', value)" type="warning" size="small">系统默认</el-tag>
              </span>
            </template>
            <el-option v-for="item in modelMap.chat" :key="item.id" :value="item.id"
              :label="modelMainLabel(item)" :disabled="item.is_active === false">
              <div flex flex-col>
                <div flex items-center gap-1>
                  <span>{{ modelMainLabel(item) }}</span>
                  <el-tag v-if="item.is_default" type="warning" size="small">系统默认</el-tag>
                  <el-tag v-if="item.is_active === false" type="info" size="small">不生效</el-tag>
                </div>
                <div text-xs text-note-sub>
                  {{ item.model }} · {{ serverTypeLabel(item.server_type) }} · {{ scopeShortLabel(item.scope) }}
                </div>
              </div>
            </el-option>
          </el-select>
          <!-- 能力标签: 最近一次测试结果(通过=能力色/失败=红), 常驻展示 -->
          <div v-if="selectedModel('chat')" class="flex items-center gap-1 flex-wrap">
            <el-tooltip v-for="cap in testedCapabilities(selectedModel('chat'))" :key="cap.key"
              :content="cap.ok ? (cap.detail || '测试通过') : (cap.error || '测试未通过')" placement="top">
              <el-tag :type="cap.ok ? (capabilityTagType[cap.key] ?? 'success') : 'danger'" size="small" effect="light">
                {{ cap.label }}
              </el-tag>
            </el-tooltip>
            <el-button link type="primary" size="small" :loading="testingType === 'chat'" @click="handleTest('chat')">
              测试能力
            </el-button>
          </div>
        </div>
      </el-form-item>

      <!-- 向量化模型绑定 -->
      <el-form-item label="向量化模型">
        <div class="w-full flex flex-col gap-1">
          <el-select v-model="displayEmbedding" placeholder="暂无系统默认公共模型, 请联系管理员配置" clearable w-full>
            <!-- 选中态自定义展示: 模型名 + 系统默认tag(与下拉选项一致) -->
            <template #label="{ value }">
              <span flex items-center gap-1>
                <span>{{ selectedText('embeddings', value) }}</span>
                <el-tag v-if="selectedIsDefault('embeddings', value)" type="warning" size="small">系统默认</el-tag>
              </span>
            </template>
            <el-option v-for="item in modelMap.embeddings" :key="item.id" :value="item.id"
              :label="modelMainLabel(item)" :disabled="item.is_active === false">
              <div flex flex-col>
                <div flex items-center gap-1>
                  <span>{{ modelMainLabel(item) }}</span>
                  <el-tag v-if="item.is_default" type="warning" size="small">系统默认</el-tag>
                  <el-tag v-if="item.is_active === false" type="info" size="small">不生效</el-tag>
                </div>
                <div text-xs text-note-sub>
                  {{ item.model }} · {{ serverTypeLabel(item.server_type) }} · {{ scopeShortLabel(item.scope) }}
                </div>
              </div>
            </el-option>
          </el-select>
          <!-- 能力标签: 最近一次测试结果(通过=能力色/失败=红), 常驻展示 -->
          <div v-if="selectedModel('embeddings')" class="flex items-center gap-1 flex-wrap">
            <el-tooltip v-for="cap in testedCapabilities(selectedModel('embeddings'))" :key="cap.key"
              :content="cap.ok ? (cap.detail || '测试通过') : (cap.error || '测试未通过')" placement="top">
              <el-tag :type="cap.ok ? (capabilityTagType[cap.key] ?? 'success') : 'danger'" size="small" effect="light">
                {{ cap.label }}
              </el-tag>
            </el-tooltip>
            <el-button link type="primary" size="small" :loading="testingType === 'embeddings'" @click="handleTest('embeddings')">
              测试能力
            </el-button>
          </div>
        </div>
      </el-form-item>

      <!-- 重排模型绑定 -->
      <el-form-item label="重排模型">
        <div class="w-full flex flex-col gap-1">
          <el-select v-model="displayRerank" placeholder="暂无系统默认公共模型, 请联系管理员配置" clearable w-full>
            <!-- 选中态自定义展示: 模型名 + 系统默认tag(与下拉选项一致) -->
            <template #label="{ value }">
              <span flex items-center gap-1>
                <span>{{ selectedText('rerank', value) }}</span>
                <el-tag v-if="selectedIsDefault('rerank', value)" type="warning" size="small">系统默认</el-tag>
              </span>
            </template>
            <el-option v-for="item in modelMap.rerank" :key="item.id" :value="item.id"
              :label="modelMainLabel(item)" :disabled="item.is_active === false">
              <div flex flex-col>
                <div flex items-center gap-1>
                  <span>{{ modelMainLabel(item) }}</span>
                  <el-tag v-if="item.is_default" type="warning" size="small">系统默认</el-tag>
                  <el-tag v-if="item.is_active === false" type="info" size="small">不生效</el-tag>
                </div>
                <div text-xs text-note-sub>
                  {{ item.model }} · {{ serverTypeLabel(item.server_type) }} · {{ scopeShortLabel(item.scope) }}
                </div>
              </div>
            </el-option>
          </el-select>
          <!-- 能力标签: 最近一次测试结果(通过=能力色/失败=红), 常驻展示 -->
          <div v-if="selectedModel('rerank')" class="flex items-center gap-1 flex-wrap">
            <el-tooltip v-for="cap in testedCapabilities(selectedModel('rerank'))" :key="cap.key"
              :content="cap.ok ? (cap.detail || '测试通过') : (cap.error || '测试未通过')" placement="top">
              <el-tag :type="cap.ok ? (capabilityTagType[cap.key] ?? 'success') : 'danger'" size="small" effect="light">
                {{ cap.label }}
              </el-tag>
            </el-tooltip>
            <el-button link type="primary" size="small" :loading="testingType === 'rerank'" @click="handleTest('rerank')">
              测试能力
            </el-button>
          </div>
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
// 模型配置的管理(新增/统计/默认公共模型配置)在 /ai/model_config 页, 仅系统管理员与授权人员使用
import { listModelConfigs, testModelCapability } from '@/modules/ai/api/model_config'
import {
  modelMainLabel,
  scopeShortLabel,
  serverTypeLabel,
  capabilityTagType,
  testedCapabilities,
} from '@/modules/ai/types/model_config'
import type { ModelConfig, ModelCapabilityResult } from '@/modules/ai/types/model_config'
import { getMyModelBinding, updateMyModelBinding } from '@/modules/rag/api/user_model'
import { ElMessage } from 'element-plus'
import type { PaginationParams } from '@/common/types/common'

// 三个可绑定的模型类型(与后端 ModelType 值对齐)
type BindableType = 'chat' | 'embeddings' | 'rerank'
const BINDABLE_TYPES: BindableType[] = ['chat', 'embeddings', 'rerank']

const loading = ref(false)
const saving = ref(false)

// 绑定表单(模型ID, null=未绑定→自动使用系统默认公共模型)
const binding = reactive<{
  chat_model_id: string | null
  embedding_model_id: string | null
  rerank_model_id: string | null
}>({
  chat_model_id: null,
  embedding_model_id: null,
  rerank_model_id: null,
})

// 各类型可见模型列表(公共/本部门/本人, 后端按当前用户过滤)
const modelMap = reactive<Record<BindableType, ModelConfig[]>>({
  chat: [],
  embeddings: [],
  rerank: [],
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

/** 模型类型 -> 绑定字段名常量表 */
const BINDING_KEYS = {
  chat: 'chat_model_id',
  embeddings: 'embedding_model_id',
  rerank: 'rerank_model_id',
} as const

/** 绑定字段名映射(类型 -> binding 键) */
const bindingKeyOf = (type: BindableType): (typeof BINDING_KEYS)[BindableType] => BINDING_KEYS[type]

/** 当前展示的模型ID: 未绑定(null)时回显系统默认公共模型(与后端实际生效一致) */
const displayValue = (type: BindableType) => binding[bindingKeyOf(type)] ?? defaultModelId(type)

/** 双向展示值: 选中默认公共模型/清除 均归一化为 null(跟随默认, 管理员更换默认后无缝切换) */
const displayBindingOf = (type: BindableType) =>
  computed<string | null>({
    get: () => displayValue(type),
    set: (v) => {
      binding[bindingKeyOf(type)] = v && v !== defaultModelId(type) ? v : null
    },
  })
// 三个下拉的 v-model 绑定(展示层回显默认公共模型, 存储层保持"null=跟随默认")
const displayChat = displayBindingOf('chat')
const displayEmbedding = displayBindingOf('embeddings')
const displayRerank = displayBindingOf('rerank')

/** 当前生效的模型配置对象(按类型, 未绑定时即默认公共模型) */
const selectedModel = (type: BindableType): ModelConfig | undefined =>
  modelMap[type].find((m) => m.id === displayValue(type))

// ################ 能力测试 ################
const testingType = ref<BindableType | null>(null)

/** 运行当前选中模型的能力测试, 结果持久化到后端并展示为标签 */
const handleTest = async (type: BindableType) => {
  const item = selectedModel(type)
  if (!item) return
  try {
    testingType.value = type
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
    testingType.value = null
  }
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

/** 初始化: 并行拉取绑定 + 三类模型列表(存储保持 null=跟随默认, 展示层负责回显默认公共模型) */
const init = async () => {
  loading.value = true
  try {
    const [bind] = await Promise.all([
      getMyModelBinding(),
      ...BINDABLE_TYPES.map((t) => fetchModels(t)),
    ])
    binding.chat_model_id = bind.chat_model_id ?? null
    binding.embedding_model_id = bind.embedding_model_id ?? null
    binding.rerank_model_id = bind.rerank_model_id ?? null
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
    await updateMyModelBinding({
      chat_model_id: binding.chat_model_id,
      embedding_model_id: binding.embedding_model_id,
      rerank_model_id: binding.rerank_model_id,
      fallback_disabled: false,
    })
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
