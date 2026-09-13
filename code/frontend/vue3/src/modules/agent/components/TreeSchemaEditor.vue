<template>
  <div class="rounded-xl border border-note bg-note-card overflow-hidden">
    <!-- 顶部: 模式切换 + 说明 -->
    <div class="flex items-center justify-between gap-2 px-3 py-2 border-b border-note bg-note-soft/60">
      <el-radio-group v-model="mode" size="small">
        <el-radio-button value="tree">树形编辑</el-radio-button>
        <el-radio-button value="json">JSON 编辑</el-radio-button>
      </el-radio-group>
      <span class="text-xs text-note-sub hidden sm:inline">
        {{ mode === 'tree' ? '展开树添加字段, 切换 JSON 可直接编辑' : '直接编辑 JSON Schema 文本' }}
      </span>
    </div>

    <!-- 树模式: 扁平渲染可见节点(缩进表层级) -->
    <div v-if="mode === 'tree'" class="p-2 max-h-72 overflow-y-auto">
      <SchemaRow
        :node="root" :depth="0" root
        @toggle="toggleNode"
        @add-child="addChild"
        @remove="removeNode"
      />
      <SchemaRow
        v-for="item in visibleRows" :key="item.node.id"
        :node="item.node" :depth="item.depth" :parent-type="item.parentType"
        @toggle="toggleNode"
        @add-child="addChild"
        @remove="removeNode"
      />
      <!-- 空树提示 -->
      <div v-if="visibleRows.length === 0" class="py-3 text-center text-xs text-note-sub">
        根对象暂无字段, 点击根节点行的 + 添加第一个字段
      </div>
    </div>

    <!-- JSON 模式: Monaco 直接编辑 -->
    <div v-else class="p-2">
      <div class="h-60 rounded-lg overflow-hidden border border-note">
        <LazyMonacoJson v-model="jsonText" language="json" class="h-full" />
      </div>
      <div v-if="jsonError" class="mt-1 text-xs text-red-500">{{ jsonError }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
// 树状 JSON Schema 编辑器(智能体输入/输出结构体配置用)
// - 树模式: 逐行编辑字段(key/类型/必填/描述), 支持嵌套对象与数组
// - JSON 模式: Monaco 直接编辑 Schema 文本, 两种模式双向同步(非法 JSON 保留原值并提示)
import { ElMessage } from 'element-plus'
import SchemaRow, { type SchemaNodeType as SchemaNode, type SchemaType } from './SchemaNodeRow.vue'

const props = defineProps<{
  /** JSON Schema 对象( null 表示未配置 ) */
  modelValue: Record<string, unknown> | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: Record<string, unknown> | null]
}>()

// Monaco 异步加载(重库独立 chunk, 与项目其他页面一致)
const LazyMonacoJson = defineAsyncComponent(
  () => import('@/common/components/ide/BaseMoacoEdit.vue'),
)

// ==================== 节点工具 ====================

let uid = 0
const nextId = () => ++uid

const newNode = (key = '', type: SchemaType = 'string'): SchemaNode => ({
  id: nextId(),
  key,
  type,
  required: false,
  description: '',
  itemType: 'string',
  children: [],
  expanded: true,
})

const root = ref<SchemaNode>(newNode('root', 'object'))

/** 该节点是否可拥有子字段(object 或 元素为对象的 array) */
const canHaveChildren = (node: SchemaNode) =>
  node.type === 'object' || (node.type === 'array' && node.itemType === 'object')

// ==================== 树 ⇄ 可见行(扁平渲染) ====================

interface VisibleRow { node: SchemaNode; depth: number; parentType: SchemaType | null }

const visibleRows = computed<VisibleRow[]>(() => {
  const rows: VisibleRow[] = []
  const walk = (children: SchemaNode[], depth: number, parentType: SchemaType | null) => {
    for (const node of children) {
      rows.push({ node, depth, parentType })
      if (canHaveChildren(node) && node.expanded && node.children.length > 0) {
        walk(node.children, depth + 1, node.type)
      }
    }
  }
  walk(root.value.children, 1, 'object')
  return rows
})

const toggleNode = (node: SchemaNode) => {
  node.expanded = !node.expanded
}

const addChild = (node: SchemaNode) => {
  if (!canHaveChildren(node)) return
  node.expanded = true
  node.children.push(newNode(`field_${node.children.length + 1}`))
}

const removeFromTree = (children: SchemaNode[], id: number): boolean => {
  const idx = children.findIndex((c) => c.id === id)
  if (idx !== -1) {
    children.splice(idx, 1)
    return true
  }
  return children.some((c) => removeFromTree(c.children, id))
}

const removeNode = (node: SchemaNode) => {
  removeFromTree(root.value.children, node.id)
}

// ==================== 树 ⇄ JSON Schema 序列化 ====================

const nodeToSchema = (node: SchemaNode): Record<string, unknown> => {
  const out: Record<string, unknown> = { type: node.type }
  if (node.description.trim()) out.description = node.description.trim()
  if (node.type === 'array') {
    out.items = node.itemType === 'object'
      ? childrenToSchema(node.children)
      : { type: node.itemType }
  }
  if (node.type === 'object') {
    Object.assign(out, childrenToSchema(node.children))
  }
  return out
}

const childrenToSchema = (children: SchemaNode[]): Record<string, unknown> => {
  const properties: Record<string, unknown> = {}
  const required: string[] = []
  for (const child of children) {
    const key = child.key.trim()
    if (!key) continue // 未命名字段不序列化
    properties[key] = nodeToSchema(child)
    if (child.required) required.push(key)
  }
  const out: Record<string, unknown> = { properties }
  if (required.length > 0) out.required = required
  return out
}

const treeToSchema = (): Record<string, unknown> => nodeToSchema(root.value)

const schemaToNode = (key: string, schema: Record<string, unknown>): SchemaNode => {
  const type = (typeof schema.type === 'string' ? schema.type : 'object') as SchemaType
  const node = newNode(key, type)
  node.description = typeof schema.description === 'string' ? schema.description : ''
  // 数组元素类型与元素字段
  if (type === 'array' && schema.items && typeof schema.items === 'object') {
    const items = schema.items as Record<string, unknown>
    const itemType = (typeof items.type === 'string' ? items.type : 'string') as SchemaType
    node.itemType = itemType
    if (itemType === 'object' && items.properties) {
      node.children = parseChildren(items)
    }
  }
  // 对象属性字段
  if (type === 'object' && schema.properties) {
    node.children = parseChildren(schema)
  }
  return node
}

const parseChildren = (schema: Record<string, unknown>): SchemaNode[] => {
  const properties = (schema.properties ?? {}) as Record<string, unknown>
  const required = Array.isArray(schema.required) ? (schema.required as string[]) : []
  return Object.entries(properties)
    .map(([key, sub]) =>
      schemaToNode(key, (sub && typeof sub === 'object' ? sub : {}) as Record<string, unknown>))
    .map((node) => ({ ...node, required: required.includes(node.key) }))
}

const schemaToTree = (schema: Record<string, unknown> | null) => {
  if (!schema || schema.type !== 'object') {
    // 未配置/非对象根: 空对象根
    root.value = newNode('root', 'object')
    return
  }
  const parsed = schemaToNode('root', schema)
  root.value = { ...parsed, key: 'root', expanded: true }
}

// ==================== 双向同步 ====================

const mode = ref<'tree' | 'json'>('tree')
const jsonText = ref('')
const jsonError = ref('')
// 内部变更标记(避免 watch 回环)
let emitting = false

// 树变更 → 序列化外发
watch(root, () => {
  if (emitting) return
  emitting = true
  emit('update:modelValue', treeToSchema())
  nextTick(() => { emitting = false })
}, { deep: true })

// 外部回填 → 重建树(编辑对话框打开时)
watch(
  () => props.modelValue,
  (value) => {
    if (emitting) return
    const current = treeToSchema()
    if (JSON.stringify(current) === JSON.stringify(value ?? {})) return
    schemaToTree(value)
  },
  { immediate: true, deep: true },
)

// 模式切换时同步两侧内容
watch(mode, (next) => {
  if (next === 'json') {
    jsonError.value = ''
    jsonText.value = JSON.stringify(treeToSchema(), null, 2)
    return
  }
  // JSON → 树: 解析失败保持 JSON 模式并提示
  const text = jsonText.value.trim()
  if (!text) {
    schemaToTree(null)
    return
  }
  try {
    const parsed = JSON.parse(text) as Record<string, unknown>
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw new Error('根节点必须是 JSON 对象')
    }
    jsonError.value = ''
    schemaToTree(parsed)
  } catch (e) {
    mode.value = 'json'
    ElMessage.warning(`JSON 解析失败: ${e instanceof Error ? e.message : '格式不正确'}`)
  }
})

// JSON 文本即时校验(仅提示, 不阻断)
watch(jsonText, (text) => {
  if (mode.value !== 'json') return
  try {
    JSON.parse(text)
    jsonError.value = ''
  } catch (e) {
    jsonError.value = e instanceof Error ? e.message : 'JSON 格式不正确'
  }
})
</script>
