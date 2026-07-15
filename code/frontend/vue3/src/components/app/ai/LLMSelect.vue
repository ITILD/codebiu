<template>
  <div flex items-center gap-2>
    <span text-sm font-medium text-gray-600>模型:</span>
    <el-select
      v-model="selectedModelId"
      placeholder="选择模型"
      w-60
      :disabled="disabled"
      @change="handleModelChange"
    >
      <el-option
        v-for="item in modelList"
        :key="item.id"
        :label="item.model"
        :value="item.id"
      />
    </el-select>
  </div>
</template>

<script setup lang="ts">
import type { ModelConfig } from '@/types/model_config'

// 组件属性定义
interface Props {
  /** 模型配置列表 */
  modelList: ModelConfig[]
  /** 当前选中的模型ID */
  modelId?: string
  /** 是否禁用选择器 */
  disabled?: boolean
}

// 组件事件定义
interface Emits {
  /** 模型选择变化事件 */
  (e: 'update:modelId', value: string): void
  /** 模型变更事件 */
  (e: 'change', value: string): void
}

// 定义属性和事件
const props = withDefaults(defineProps<Props>(), {
  modelList: () => [],
  modelId: '',
  disabled: false
})

const emit = defineEmits<Emits>()

// 内部选中的模型ID
const selectedModelId = ref(props.modelId)

// 监听外部modelId变化
watch(() => props.modelId, (newValue) => {
  selectedModelId.value = newValue
})

// 处理模型选择变化
const handleModelChange = (value: string) => {
  emit('update:modelId', value)
  emit('change', value)
}

// 暴露方法：获取当前选中的模型
const getSelectedModel = () => {
  return props.modelList.find(item => item.id === selectedModelId.value)
}

// 暴露方法：设置选中的模型
const setSelectedModel = (modelId: string) => {
  selectedModelId.value = modelId
  handleModelChange(modelId)
}

// 暴露组件方法
defineExpose({
  getSelectedModel,
  setSelectedModel
})
</script>
