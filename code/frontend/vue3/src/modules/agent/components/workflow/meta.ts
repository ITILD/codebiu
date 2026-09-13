// src/modules/agent/components/workflow/meta.ts
// 工作流节点类型元信息(编辑器面板/画布节点/轨迹展示共用)

import { Promotion, Finished, MagicStick, Filter, Document } from '@element-plus/icons-vue'
import type { Component } from 'vue'
import type { WorkflowNodeType } from '../../types'

/** 节点类型元信息 */
export interface NodeTypeMeta {
  label: string
  /** 描述(节点面板用) */
  desc: string
  icon: Component
  /** 主题色(UnoCSS note 色板) */
  tintClass: string
  iconClass: string
  borderClass: string
}

/** 五类节点的展示元信息(与后端 NODE_TYPES 对齐) */
export const NODE_TYPE_META: Record<WorkflowNodeType, NodeTypeMeta> = {
  start: {
    label: '开始',
    desc: '工作流入口, 运行输入从这里进入',
    icon: Promotion,
    tintClass: 'bg-green-500/10',
    iconClass: 'text-green-600',
    borderClass: 'border-green-400/60',
  },
  end: {
    label: '结束',
    desc: '工作流出口, 产出最终结果',
    icon: Finished,
    tintClass: 'bg-red-500/10',
    iconClass: 'text-red-500',
    borderClass: 'border-red-400/60',
  },
  llm: {
    label: 'LLM',
    desc: '大模型推理节点, 支持 JSON 结构化输出',
    icon: MagicStick,
    tintClass: 'bg-violet-500/10',
    iconClass: 'text-violet-500',
    borderClass: 'border-violet-400/60',
  },
  condition: {
    label: '条件分支',
    desc: '按条件走 是/否 两条分支',
    icon: Filter,
    tintClass: 'bg-amber-500/10',
    iconClass: 'text-amber-600',
    borderClass: 'border-amber-400/60',
  },
  template: {
    label: '模板拼接',
    desc: '引用上游输出拼接文本',
    icon: Document,
    tintClass: 'bg-sky-500/10',
    iconClass: 'text-sky-600',
    borderClass: 'border-sky-400/60',
  },
}

/** 条件节点支持的运算符 */
export const CONDITION_OPERATORS: Array<{ value: string; label: string }> = [
  { value: 'eq', label: '等于' },
  { value: 'ne', label: '不等于' },
  { value: 'gt', label: '大于' },
  { value: 'gte', label: '大于等于' },
  { value: 'lt', label: '小于' },
  { value: 'lte', label: '小于等于' },
  { value: 'contains', label: '包含' },
  { value: 'empty', label: '为空' },
  { value: 'regex', label: '正则匹配' },
]
