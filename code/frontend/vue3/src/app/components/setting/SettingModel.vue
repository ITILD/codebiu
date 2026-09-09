<template>
  <div max-w-[640px] flex flex-col gap-5>
    <div>
      <h3 text-lg font-medium text-note m-0>模型设置</h3>
      <p text-sm text-note-sub mt-1 mb-0>
        绑定个人默认模型(可选用公共/本部门/自己的模型); 未绑定的类型自动使用系统默认公共模型
      </p>
    </div>

    <el-form v-loading="loading" label-width="96px" label-position="right" flex flex-col gap-1>
      <!-- 对话模型绑定 -->
      <el-form-item label="对话模型">
        <div w-full flex flex-col gap-1>
          <el-select v-model="binding.chat_model_id" placeholder="未绑定(使用系统默认公共模型)" clearable w-full>
            <el-option v-for="item in modelMap.chat" :key="item.id" :value="item.id"
              :label="optionLabel(item)" :disabled="item.is_active === false">
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
          <div v-if="defaultHint.chat" text-xs text-note-sub>
            系统默认公共模型: {{ defaultHint.chat }}(未绑定时回退使用)
          </div>
        </div>
      </el-form-item>

      <!-- 向量化模型绑定 -->
      <el-form-item label="向量化模型">
        <div w-full flex flex-col gap-1>
          <el-select v-model="binding.embedding_model_id" placeholder="未绑定(使用系统默认公共模型)" clearable w-full>
            <el-option v-for="item in modelMap.embeddings" :key="item.id" :value="item.id"
              :label="optionLabel(item)" :disabled="item.is_active === false">
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
          <div v-if="defaultHint.embeddings" text-xs text-note-sub>
            系统默认公共模型: {{ defaultHint.embeddings }}(未绑定时回退使用)
          </div>
        </div>
      </el-form-item>

      <!-- 重排模型绑定 -->
      <el-form-item label="重排模型">
        <div w-full flex flex-col gap-1>
          <el-select v-model="binding.rerank_model_id" placeholder="未绑定(使用系统默认公共模型)" clearable w-full>
            <el-option v-for="item in modelMap.rerank" :key="item.id" :value="item.id"
              :label="optionLabel(item)" :disabled="item.is_active === false">
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
          <div v-if="defaultHint.rerank" text-xs text-note-sub>
            系统默认公共模型: {{ defaultHint.rerank }}(未绑定时回退使用)
          </div>
        </div>
      </el-form-item>

      <!-- 回退开关(v4 4.3): 绑定失效时是否回退默认公共模型 -->
      <el-form-item label="回退兜底">
        <div w-full flex flex-col gap-1>
          <el-switch v-model="allowFallback" active-text="绑定失效时回退系统默认公共模型" />
          <div text-xs text-note-sub leading-5>
            <template v-if="allowFallback">
              开启: 绑定的模型被删除/取消共享等失效时, 自动改用系统默认公共模型处理(数据将流向公共模型, 请求时会提示)
            </template>
            <template v-else>
              关闭: 绑定失效时直接报错, 数据不会流向公共模型(数据流向可感知)
            </template>
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
// 设置页-模型设置面板: 用户级模型绑定/切换 + 回退开关(v4 4.3)
// 模型配置的管理(新增/统计/默认公共模型配置)在 /ai/model_config 页, 仅系统管理员与授权人员使用
import { listModelConfigs } from '@/modules/ai/api/model_config'
import { modelMainLabel, scopeShortLabel, serverTypeLabel } from '@/modules/ai/types/model_config'
import type { ModelConfig } from '@/modules/ai/types/model_config'
import { getMyModelBinding, updateMyModelBinding } from '@/modules/rag/api/user_model'
import { ElMessage } from 'element-plus'
import type { PaginationParams } from '@/common/types/common'

// 三个可绑定的模型类型(与后端 ModelType 值对齐)
type BindableType = 'chat' | 'embeddings' | 'rerank'
const BINDABLE_TYPES: BindableType[] = ['chat', 'embeddings', 'rerank']

const loading = ref(false)
const saving = ref(false)

// 绑定表单(模型ID, null=未绑定)
const binding = reactive<{
  chat_model_id: string | null
  embedding_model_id: string | null
  rerank_model_id: string | null
  fallback_disabled: boolean
}>({
  chat_model_id: null,
  embedding_model_id: null,
  rerank_model_id: null,
  fallback_disabled: false,
})

// 回退开关的界面语义与后端 fallback_disabled 相反: 允许回退=true
const allowFallback = computed({
  get: () => !binding.fallback_disabled,
  set: (v: boolean) => { binding.fallback_disabled = !v },
})

// 各类型可见模型列表(公共/本部门/本人, 后端按当前用户过滤)
const modelMap = reactive<Record<BindableType, ModelConfig[]>>({
  chat: [],
  embeddings: [],
  rerank: [],
})

// 各类型当前生效的默认公共模型名(回退目标提示)
const defaultHint = computed<Record<BindableType, string>>(() => {
  const hint = { chat: '', embeddings: '', rerank: '' } as Record<BindableType, string>
  for (const type of BINDABLE_TYPES) {
    const found = modelMap[type].find(
      (m) => m.is_default && m.is_active !== false && m.scope === 'public'
    )
    hint[type] = found ? modelMainLabel(found) : ''
  }
  return hint
})

/** 下拉选项主文案(默认模型附加标注) */
const optionLabel = (item: ModelConfig) =>
  item.is_default ? `${modelMainLabel(item)}(系统默认)` : modelMainLabel(item)

/** 拉取单个类型的可见模型列表 */
const fetchModels = async (type: BindableType) => {
  try {
    const res = await listModelConfigs({ page: 1, size: 200, model_type: type } as PaginationParams)
    modelMap[type] = res.items
  } catch (error) {
    console.error(`获取${type}模型列表失败:`, error)
  }
}

/** 初始化: 并行拉取绑定 + 三类模型列表 */
const init = async () => {
  loading.value = true
  try {
    const [bind] = await Promise.all([
      getMyModelBinding(),
      ...BINDABLE_TYPES.map((t) => fetchModels(t)),
    ])
    binding.chat_model_id = bind.chat_model_id
    binding.embedding_model_id = bind.embedding_model_id
    binding.rerank_model_id = bind.rerank_model_id
    binding.fallback_disabled = bind.fallback_disabled ?? false
  } catch (error) {
    console.error('获取模型绑定失败:', error)
    ElMessage.error('获取模型绑定失败')
  } finally {
    loading.value = false
  }
}

/** 保存绑定(绑定前校验由后端完成: 公共/本部门/本人模型才允许绑定) */
const handleSave = async () => {
  try {
    saving.value = true
    await updateMyModelBinding({
      chat_model_id: binding.chat_model_id,
      embedding_model_id: binding.embedding_model_id,
      rerank_model_id: binding.rerank_model_id,
      fallback_disabled: binding.fallback_disabled,
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
