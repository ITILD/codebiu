<template>
  <!-- 工作流画布节点: 按类型渲染图标/标题/摘要, 内置连线锚点 -->
  <div
    class="w-44 rounded-xl border-2 bg-note-card shadow-note transition-all cursor-pointer"
    :class="[meta.borderClass, selected ? 'ring-2 ring-note-green shadow-note-hover' : 'hover:shadow-note-hover']"
    @dblclick.stop
  >
    <Handle v-if="hasTarget" type="target" :position="Position.Top" class="!w-2.5 !h-2.5 !bg-note-green !border-2 !border-white" />

    <!-- 标题行 -->
    <div class="flex items-center gap-2 px-3 pt-2.5 pb-1.5">
      <div class="w-6 h-6 rounded-lg flex-center shrink-0" :class="meta.tintClass">
        <el-icon :size="13" :class="meta.iconClass"><component :is="meta.icon" /></el-icon>
      </div>
      <span class="text-xs font-bold text-note">{{ meta.label }}</span>
      <span class="ml-auto text-[10px] text-note-sub/60 font-mono">{{ id }}</span>
    </div>

    <!-- 摘要(按类型展示关键配置) -->
    <div class="px-3 pb-2.5">
      <p class="text-[11px] leading-relaxed text-note-sub m-0 line-clamp-2 break-all">
        {{ summary || meta.desc }}
      </p>
      <!-- 条件节点: 是/否 双分支出锚 -->
      <div v-if="nodeType === 'condition'" class="flex gap-2 mt-1 text-[10px]">
        <span class="px-1.5 py-0.5 rounded bg-green-500/10 text-green-600">是</span>
        <span class="px-1.5 py-0.5 rounded bg-red-500/10 text-red-500">否</span>
      </div>
    </div>

    <!-- 条件节点双出锚(true/false), 其余单出锚 -->
    <template v-if="nodeType === 'condition'">
      <Handle id="true" type="source" :position="Position.Bottom" class="!left-1/4 !w-2.5 !h-2.5 !bg-green-500 !border-2 !border-white" />
      <Handle id="false" type="source" :position="Position.Bottom" class="!left-3/4 !w-2.5 !h-2.5 !bg-red-400 !border-2 !border-white" />
    </template>
    <Handle v-else-if="hasSource" type="source" :position="Position.Bottom" class="!w-2.5 !h-2.5 !bg-note-green !border-2 !border-white" />
  </div>
</template>

<script setup lang="ts">
// Vue Flow 自定义节点渲染(五种业务类型共用, 由 node.type 区分)
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { NODE_TYPE_META } from './meta'
import type { WorkflowNode } from '../../types'

const props = defineProps<{
  /** 节点ID(展示用短标识) */
  id: string
  /** Vue Flow 节点数据(业务类型与配置在 data) */
  data: WorkflowNode['data'] & { nodeType?: string }
  /** 画布节点类型(即业务类型) */
  type: string
  selected?: boolean
}>()

const nodeType = computed(() => props.type as keyof typeof NODE_TYPE_META)
const meta = computed(() => NODE_TYPE_META[nodeType.value] ?? NODE_TYPE_META.llm)

/** 开始节点只有出锚, 结束节点只有入锚, 其余双向 */
const hasTarget = computed(() => nodeType.value !== 'start')
const hasSource = computed(() => nodeType.value !== 'end')

// 节点摘要: 展示各类型的关键配置
const summary = computed(() => {
  const d = props.data || {}
  if (nodeType.value === 'llm') {
    const text = (d.prompt || '').replace(/\s+/g, ' ').trim()
    return text ? `提示词: ${text}` : ''
  }
  if (nodeType.value === 'template') {
    const text = (d.template || '').replace(/\s+/g, ' ').trim()
    return text || ''
  }
  if (nodeType.value === 'condition') {
    const op = (d.operator || '').trim()
    return d.left_source ? `{{${d.left_source}${d.left_path ? '.' + d.left_path : ''}}} ${op} ${d.right ?? ''}` : ''
  }
  if (nodeType.value === 'end') {
    return d.result ? `输出: ${d.result}` : '取最后 LLM 节点输出'
  }
  return ''
})
</script>
