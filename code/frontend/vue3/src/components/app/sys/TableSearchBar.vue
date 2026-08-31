<script lang="ts">
// 导出类型供各列表页面使用
export interface SearchFieldOption {
  label: string
  value: string | number | boolean
}

/** 搜索字段配置 */
export interface SearchField {
  /** 查询参数键名(对应 v-model 对象的字段) */
  prop: string
  /** 字段标签 */
  label: string
  /** 控件类型: input=文本(默认) / select=下拉选择 */
  type?: 'input' | 'select'
  /** 占位提示 */
  placeholder?: string
  /** select 类型的选项列表 */
  options?: SearchFieldOption[]
  /** 控件宽度(CSS 值, 默认 180px) */
  width?: string
}
</script>

<!--
  统一表格搜索栏组件(参考主流 SaaS 系统多字段筛选风格)
  - 支持文本输入 / 下拉选择两类筛选字段
  - 搜索 / 重置按钮, 字段较多时支持展开/收起
  - 右侧 actions 插槽用于放置"新增"等主操作按钮
  用法示例:
  <TableSearchBar v-model="queryParams" :fields="searchFields"
    @search="handleSearch" @reset="handleSearch">
    <template #actions>
      <el-button type="primary" @click="handleCreate">新增用户</el-button>
    </template>
  </TableSearchBar>
-->
<template>
  <div p-4 mb-4 rounded-lg bg-note-card border border-note shadow-note>
    <div flex flex-wrap items-center gap-x-4 gap-y-3>
      <!-- 筛选字段区 -->
      <div v-for="field in visibleFields" :key="field.prop" flex items-center gap-2>
        <span text-sm text-note whitespace-nowrap>{{ field.label }}</span>

        <!-- 文本输入框: 回车/清空后触发搜索 -->
        <el-input
          v-if="!field.type || field.type === 'input'"
          :model-value="(modelValue[field.prop] as string | undefined) ?? ''"
          :placeholder="field.placeholder ?? `请输入${field.label}`"
          :style="{ width: field.width ?? '180px' }"
          clearable
          @update:model-value="(val: string) => setValue(field.prop, val)"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        />

        <!-- 下拉选择: 选择后立即触发搜索 -->
        <el-select
          v-else-if="field.type === 'select'"
          :model-value="(modelValue[field.prop] as string | number | boolean | undefined)"
          :placeholder="field.placeholder ?? `全部${field.label}`"
          :style="{ width: field.width ?? '160px' }"
          clearable
          @update:model-value="(val: string | number | boolean) => {
            setValue(field.prop, val)
            handleSearch()
          }"
        >
          <el-option
            v-for="opt in field.options ?? []"
            :key="String(opt.value)"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
      </div>

      <!-- 操作按钮区: 搜索/重置/展开 + 主操作插槽 -->
      <div flex items-center gap-2 ml-auto>
        <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
        <el-button :icon="RefreshLeft" @click="handleReset">重置</el-button>
        <el-button
          v-if="fields.length > collapseCount"
          link type="primary"
          @click="expanded = !expanded"
        >
          {{ expanded ? '收起' : '展开' }}
          <el-icon class="transition-transform" :class="expanded ? 'rotate-180' : ''">
            <ArrowDown />
          </el-icon>
        </el-button>
        <slot name="actions" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Search, RefreshLeft, ArrowDown } from '@element-plus/icons-vue'

const props = withDefaults(
  defineProps<{
    /** 查询参数对象(建议页面使用 ref 包裹) */
    modelValue: Record<string, unknown>
    /** 筛选字段配置 */
    fields: SearchField[]
    /** 收起状态下可见的字段数量 */
    collapseCount?: number
  }>(),
  { collapseCount: 3 }
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: Record<string, unknown>): void
  (e: 'search'): void
  (e: 'reset'): void
}>()

// 展开/收起状态
const expanded = ref(false)

// 收起时仅显示前 collapseCount 个字段
const visibleFields = computed(() =>
  expanded.value ? props.fields : props.fields.slice(0, props.collapseCount)
)

// 更新单个查询参数(不可变更新, 触发父组件 v-model)
const setValue = (prop: string, value: unknown) => {
  emit('update:modelValue', { ...props.modelValue, [prop]: value })
}

// 触发搜索
const handleSearch = () => emit('search')

// 重置: 仅清空 fields 中声明的字段, 保留分页等其他参数
const handleReset = () => {
  const next = { ...props.modelValue }
  for (const field of props.fields) {
    next[field.prop] = undefined
  }
  emit('update:modelValue', next)
  emit('reset')
}
</script>
