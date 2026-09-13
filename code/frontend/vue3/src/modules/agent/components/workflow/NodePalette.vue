<template>
  <!-- 左侧节点面板: 拖入画布或点击添加 -->
  <div class="w-52 shrink-0 border-r border-note bg-note-card/60 flex flex-col">
    <div class="px-3 py-2.5 border-b border-note">
      <span class="text-sm font-bold text-note">节点</span>
      <p class="text-[11px] text-note-sub m-0 mt-0.5">拖拽到画布, 或点击添加</p>
    </div>
    <div class="p-2.5 flex flex-col gap-2 overflow-y-auto">
      <div
        v-for="(item, key) in NODE_TYPE_META" :key="key"
        class="flex items-start gap-2.5 p-2.5 rounded-xl bg-note-card border border-note cursor-grab
               hover:shadow-note hover:-translate-y-0.5 active:cursor-grabbing transition-all"
        draggable="true"
        @dragstart="onDragStart(key as WorkflowNodeType, $event)"
        @click="$emit('add', key as WorkflowNodeType)"
      >
        <div class="w-8 h-8 rounded-lg flex-center shrink-0" :class="item.tintClass">
          <el-icon :size="16" :class="item.iconClass"><component :is="item.icon" /></el-icon>
        </div>
        <div class="min-w-0">
          <div class="text-xs font-medium text-note">{{ item.label }}</div>
          <p class="text-[11px] text-note-sub m-0 leading-snug line-clamp-2">{{ item.desc }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// 工作流节点面板(五种节点类型, HTML5 拖拽 + 点击添加)
import { NODE_TYPE_META } from './meta'
import type { WorkflowNodeType } from '../../types'

const emit = defineEmits<{
  /** 点击添加节点 */
  add: [type: WorkflowNodeType]
}>()

// 拖拽开始: 类型写入 dataTransfer, 画布 drop 时读取
const onDragStart = (type: WorkflowNodeType, event: DragEvent) => {
  event.dataTransfer?.setData('application/agent-node-type', type)
  event.dataTransfer!.effectAllowed = 'move'
}
</script>
