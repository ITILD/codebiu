<template>
  <!-- 单个字段行: 缩进 + 展开箭头 + 字段名 + 类型 + 必填 + 描述 + 操作 -->
  <div
    class="flex flex-wrap items-center gap-1.5 py-1 rounded-lg"
    :class="root ? '' : 'hover:bg-note-tint/50'"
    :style="{ paddingLeft: `${depth * 16}px` }"
  >
    <!-- 展开箭头(有子字段时) -->
    <button
      v-if="canHaveChildren(node)"
      class="w-5 h-5 flex-center rounded text-note-sub hover:bg-note-tint transition"
      :title="node.expanded ? '收起' : '展开'"
      @click="$emit('toggle', node)"
    >
      <el-icon :size="12" class="transition-transform" :class="node.expanded ? 'rotate-90' : ''">
        <CaretRight />
      </el-icon>
    </button>
    <span v-else class="w-5 shrink-0" />

    <!-- 字段名 -->
    <el-input
      v-if="!root" v-model="node.key" size="small"
      class="w-28" placeholder="字段名" maxlength="50"
    />
    <span v-else class="text-xs font-medium text-note-sub px-1">根对象(object)</span>

    <!-- 类型 -->
    <el-select v-if="!root" v-model="node.type" size="small" class="w-24">
      <el-option v-for="opt in typeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
    </el-select>

    <!-- 数组元素类型 -->
    <el-select
      v-if="node.type === 'array'" v-model="node.itemType" size="small"
      class="w-28" title="数组元素类型"
    >
      <el-option v-for="opt in typeOptions" :key="opt.value" :label="`元素: ${opt.label}`" :value="opt.value" />
    </el-select>

    <!-- 必填(仅对象字段; 数组元素字段无必填语义) -->
    <el-checkbox
      v-if="!root && parentType !== 'array'" v-model="node.required" size="small"
      class="mr-1" title="该字段是否必填"
    >
      <span class="text-xs text-note-sub">必填</span>
    </el-checkbox>

    <!-- 描述 -->
    <el-input
      v-model="node.description" size="small" class="flex-1 min-w-24"
      placeholder="描述(可选)" maxlength="100"
    />

    <!-- 操作: 添加子字段 / 删除 -->
    <div v-if="!root" class="flex items-center gap-0.5 shrink-0">
      <button
        v-if="canHaveChildren(node)"
        class="w-6 h-6 flex-center rounded-md text-note-sub hover:bg-note-tint hover:text-note-green transition"
        title="添加子字段" @click="$emit('add-child', node)"
      >
        <el-icon :size="14"><Plus /></el-icon>
      </button>
      <button
        class="w-6 h-6 flex-center rounded-md text-note-sub hover:bg-red-500/10 hover:text-red-500 transition"
        title="删除字段" @click="$emit('remove', node)"
      >
        <el-icon :size="14"><Delete /></el-icon>
      </button>
    </div>
    <div v-else class="flex items-center shrink-0">
      <button
        class="w-6 h-6 flex-center rounded-md text-note-sub hover:bg-note-tint hover:text-note-green transition"
        title="添加根字段" @click="$emit('add-child', node)"
      >
        <el-icon :size="14"><Plus /></el-icon>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
// 树状 Schema 编辑器的单行节点(扁平渲染, 逻辑状态由父组件持有)
import { CaretRight, Plus, Delete } from '@element-plus/icons-vue'

/** 字段类型(与 JSON Schema 基础类型对齐) */
export type SchemaType = 'string' | 'integer' | 'number' | 'boolean' | 'object' | 'array'

/** 树节点(序列化为 JSON Schema 的中间结构, 与父组件共享) */
export interface SchemaNodeType {
  id: number
  key: string
  type: SchemaType
  required: boolean
  description: string
  itemType: SchemaType
  children: SchemaNodeType[]
  expanded: boolean
}

defineProps<{
  node: SchemaNodeType
  depth: number
  /** 根节点行(不可删除/改名, 固定 object) */
  root?: boolean
  /** 父节点类型(object 字段可必填, 数组元素字段不可) */
  parentType?: string | null
}>()

defineEmits<{
  toggle: [node: SchemaNodeType]
  'add-child': [node: SchemaNodeType]
  remove: [node: SchemaNodeType]
}>()

/** 该节点是否可拥有子字段(object 或 元素为对象的 array) */
const canHaveChildren = (node: SchemaNodeType) =>
  node.type === 'object' || (node.type === 'array' && node.itemType === 'object')

const typeOptions = [
  { label: '字符串', value: 'string' },
  { label: '整数', value: 'integer' },
  { label: '数字', value: 'number' },
  { label: '布尔', value: 'boolean' },
  { label: '对象', value: 'object' },
  { label: '数组', value: 'array' },
]
</script>
