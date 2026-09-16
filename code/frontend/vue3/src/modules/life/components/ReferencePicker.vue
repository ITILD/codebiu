<template>
  <!-- 取名参考体系多选卡片(民俗/神话), 选中态以浅底色差+光晕环高亮(无描边) -->
  <div>
    <!-- 快捷操作行 -->
    <div flex flex-wrap items-center gap-2 mb-2>
      <span text-xs text-note-sub>已选 {{ modelValue.length }}/{{ catalog.length }}</span>
      <el-button size="small" text bg type="primary" plain :disabled="disabled" @click="selectStrict">
        仅严格推算
      </el-button>
      <el-button size="small" text bg type="primary" plain :disabled="disabled" @click="selectAll">
        全选
      </el-button>
      <el-button size="small" text bg :disabled="disabled || !modelValue.length" @click="clear">
        清空
      </el-button>
    </div>

    <!-- 多选卡片栅格: 无描边, 选中仅以浅底+光晕环高亮 -->
    <div grid grid-cols-2 gap-2>
      <button
        v-for="ref in catalog" :key="ref.key"
        type="button"
        class="note-transition text-left rounded-note-md p-2.5 cursor-pointer"
        :class="isSelected(ref.key)
          ? 'bg-note-tint shadow-note'
          : 'bg-note-card hover:bg-note-tint/60'"
        :disabled="disabled"
        @click="toggle(ref.key)"
      >
        <div flex items-center gap-1.5>
          <span text-base leading-none>{{ ref.icon }}</span>
          <span text-sm font-medium text-note>{{ ref.label }}</span>
          <span ml-auto text-10px leading-none py-0.5 whitespace-nowrap
            :class="ref.strict ? 'text-note-green' : 'text-note-sub'">
            {{ ref.strict ? '严格推算' : '风格参考' }}
          </span>
        </div>
        <div mt-1 text-xs text-note-sub leading-snug>{{ ref.desc }}</div>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
/** 参考体系多选器: 卡片点选切换, 提供全选/仅严格推算/清空快捷操作 */
import type { FolkReferenceItem, ReferenceKey } from '../types/baby_name'

const props = defineProps<{
  /** 参考体系目录(后端 /references 返回) */
  catalog: FolkReferenceItem[]
  /** 已选参考 key 列表 */
  modelValue: ReferenceKey[]
  /** 禁用(生成中) */
  disabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: ReferenceKey[]): void
}>()

/** 是否已选中 */
const isSelected = (key: ReferenceKey) => props.modelValue.includes(key)

/** 切换选中态 */
const toggle = (key: ReferenceKey) => {
  const next = isSelected(key)
    ? props.modelValue.filter((k) => k !== key)
    : [...props.modelValue, key]
  emit('update:modelValue', next)
}

/** 全选 */
const selectAll = () => emit('update:modelValue', props.catalog.map((r) => r.key))

/** 仅选中带经典计算的五项 */
const selectStrict = () =>
  emit('update:modelValue', props.catalog.filter((r) => r.strict).map((r) => r.key))

/** 清空 */
const clear = () => emit('update:modelValue', [])
</script>
