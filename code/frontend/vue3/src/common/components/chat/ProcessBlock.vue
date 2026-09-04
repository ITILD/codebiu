<script setup lang="ts">
// 助手消息"过程区块"折叠展示: 推理过程/意图分析/知识检索引用溯源等
// - 按 stream_event_type 显示小标题与图标
// - 知识检索(tool_call)解析引用条目: 来源文件 + 相关度 + 摘要
// - 流式进行中默认展开, 结束后自动折叠为单行入口
import { computed, watch } from 'vue'
import type { MessageBlock } from '@/common/types/chat'
import { StreamEventType, STREAM_TYPE_LABELS } from '@/common/types/chat'
import {
  MagicStick, Search, DataLine, Link, Document, Warning, ArrowRight,
} from '@element-plus/icons-vue'
import MarkdownContent from './MarkdownContent.vue'

interface Props {
  /** 该条助手消息的过程区块列表 */
  blocks: MessageBlock[]
  /** 是否处于流式接收中(影响默认展开) */
  streaming?: boolean
}

const props = defineProps<Props>()

// 区块类型 → 图标组件
const TYPE_ICONS: Record<string, unknown> = {
  [StreamEventType.LLM_THINKING]: MagicStick,
  [StreamEventType.AGENT_THINKING]: MagicStick,
  [StreamEventType.AGENT_THINKING_CONCLUSION]: DataLine,
  [StreamEventType.TOOL_CALL]: Search,
  [StreamEventType.FILE_GEN]: Document,
  [StreamEventType.STATUS]: Link,
  [StreamEventType.ERROR]: Warning,
}

const blockTitle = (block: MessageBlock): string =>
  STREAM_TYPE_LABELS[block.stream_event_type ?? ''] ?? '过程信息'

const blockIcon = (block: MessageBlock): unknown =>
  TYPE_ICONS[block.stream_event_type ?? ''] ?? Link

/* ===== 知识检索引用解析 ===== */
/** 单条引用: 来源文档 + 相关度 + 内容摘要 */
interface Citation {
  source: string
  score: string
  summary: string
}

// 匹配后端检索输出行: "1. [来源] (相关度 0.872) 摘要…"
const CITATION_LINE_RE = /^\d+\.\s*\[(.*?)\]\s*\(相关度\s*([\d.\-*]+)\)\s*(.*)$/

/** 从 tool_call 文本解析引用列表(解析失败返回 null, 走通用 markdown 渲染) */
const parseCitations = (content: string): Citation[] | null => {
  const lines = content
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)
  // 首行应为 "检索到 N 条相关片段" 概述
  if (!/^检索到\s*\d+\s*条/.test(lines[0] ?? '')) return null
  const citations: Citation[] = []
  for (const line of lines.slice(1)) {
    const m = line.match(CITATION_LINE_RE)
    if (m) citations.push({ source: m[1], score: m[2], summary: m[3] })
  }
  return citations.length > 0 ? citations : null
}

/** 各区块的引用解析结果(type → citations) */
const citationMap = computed(() => {
  const map = new Map<string, Citation[]>()
  for (const block of props.blocks ?? []) {
    if (block.stream_event_type === StreamEventType.TOOL_CALL) {
      const citations = parseCitations(block.content)
      if (citations) map.set(block.id, citations)
    }
  }
  return map
})

/** 相关度 → 进度条百分比 */
const scorePercent = (score: string): number => {
  const n = parseFloat(score)
  return Number.isFinite(n) ? Math.max(0, Math.min(1, n)) * 100 : 0
}

/** 某区块是否有引用解析结果 */
const hasCitations = (blockId: string): boolean => citationMap.value.has(blockId)

const getCitations = (blockId: string): Citation[] => citationMap.value.get(blockId) ?? []

/* ===== 折叠状态 ===== */
const collapsed = ref(true)

// 流式期间自动展开(看到实时过程), 流式结束后折叠
watch(
  () => props.streaming,
  (streaming) => { collapsed.value = !streaming },
  { immediate: true },
)

const toggle = () => { collapsed.value = !collapsed.value }
</script>

<template>
  <div v-if="blocks?.length" class="pb-wrap">
    <!-- 折叠头: 摘要入口(点击展开/收起) -->
    <button class="pb-head" :class="{ open: !collapsed }" @click="toggle">
      <el-icon :size="14" class="pb-icon"><MagicStick /></el-icon>
      <span class="pb-label">思考与检索过程</span>
      <span class="pb-count">{{ blocks.length }} 个步骤</span>
      <el-icon :size="12" class="pb-arrow" :class="{ open: !collapsed }">
        <ArrowRight />
      </el-icon>
    </button>

    <!-- 展开内容: 每个过程区块一张小卡 -->
    <div v-show="!collapsed" class="pb-body">
      <div v-for="block in blocks" :key="block.id" class="pb-item">
        <div class="pb-item-title">
          <el-icon :size="13">
            <component :is="blockIcon(block)" />
          </el-icon>
          <span>{{ blockTitle(block) }}</span>
        </div>

        <!-- 引用溯源卡片(知识检索) -->
        <template v-if="hasCitations(block.id)">
          <div
            v-for="(c, i) in getCitations(block.id)"
            :key="i"
            class="pb-citation"
          >
            <div class="pb-cite-head">
              <el-icon :size="12"><Document /></el-icon>
              <span class="pb-cite-source" :title="c.source">{{ c.source }}</span>
              <span class="pb-cite-score">{{ c.score }}</span>
            </div>
            <el-progress
              :percentage="scorePercent(c.score)"
              :stroke-width="3"
              :show-text="false"
              class="pb-cite-bar"
            />
            <p class="pb-cite-summary">{{ c.summary }}</p>
          </div>
        </template>

        <!-- 通用 markdown 内容(推理/意图分析等) -->
        <MarkdownContent v-else :content="block.content" :block-id="`pb-${block.id}`" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.pb-wrap {
  margin-bottom: 10px;
  border: 1px dashed var(--note-border, #e2e8e3);
  border-radius: 10px;
  background: var(--note-soft, #f6faf5);
  overflow: hidden;
}

.pb-head {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 6px 12px;
  border: none;
  background: transparent;
  color: var(--note-sub, #6b7f6e);
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s;
}

.pb-head:hover,
.pb-head.open {
  background: var(--note-tint, #e7f3e9);
  color: var(--note-green-deep, #3f7a52);
}

.pb-icon {
  flex-shrink: 0;
}

.pb-label {
  font-weight: 500;
}

.pb-count {
  opacity: 0.7;
}

.pb-arrow {
  margin-left: auto;
  transition: transform 0.2s;
}

.pb-arrow.open {
  transform: rotate(90deg);
}

.pb-body {
  padding: 6px 10px 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.pb-item {
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--note-card, #fdfefc);
  border: 1px solid var(--note-border, #e2e8e3);
}

.pb-item-title {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-bottom: 4px;
  font-size: 12px;
  font-weight: 600;
  color: var(--note-green-deep, #3f7a52);
}

/* 引用溯源卡片 */
.pb-citation {
  padding: 6px 8px;
  border-radius: 6px;
  background: var(--note-soft, #f6faf5);
  margin-top: 6px;
}

.pb-cite-head {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
}

.pb-cite-source {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--note-green-deep, #3f7a52);
  font-weight: 500;
}

.pb-cite-score {
  flex-shrink: 0;
  font-size: 11px;
  color: var(--note-sub, #6b7f6e);
  font-family: ui-monospace, Consolas, monospace;
}

.pb-cite-bar {
  margin: 4px 0 2px;
}

.pb-cite-bar :deep(.el-progress-bar__outer) {
  background: var(--note-border, #e2e8e3);
}

.pb-cite-summary {
  margin: 2px 0 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--el-text-color-regular, #4e5f52);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
