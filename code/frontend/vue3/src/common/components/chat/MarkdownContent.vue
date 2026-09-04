<script setup lang="ts">
// Markdown 富文本渲染区块:
// 1. 先保护 $..$ / $$..$$ 公式占位(避免 markdown 语法与公式互相干扰), 渲染后用 katex 恢复
// 2. 按 token 分段: mermaid 代码块 → MermaidBlock, 表格 → TableBlock, 其余 → v-html 文本段
import { computed } from 'vue'
import { marked, type Tokens } from 'marked'
import MermaidBlock from './MermaidBlock.vue'
import TableBlock from './TableBlock.vue'
import { protectMath, restoreMathHtml } from '@/common/utils/latex'

interface Props {
  /** markdown 源内容 */
  content: string
  /** 所属消息/区块唯一ID(用于生成子块ID) */
  blockId: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'update:mermaid-code', payload: { id: string; code: string }): void
}>()

type SegType = 'text' | 'mermaid' | 'table'

interface Segment {
  type: SegType
  content: string
  id: string
  code?: string
}

/** 表格 token 还原为 markdown 文本(交给 TableBlock 渲染) */
const buildTableMarkdown = (token: Tokens.Table): string => {
  const header = `| ${token.header.map((t) => t.text).join(' | ')} |\n`
  const alignRow =
    `| ${token.align
      .map((a) => (a === 'center' ? ':---:' : a === 'right' ? '---:' : '---'))
      .join(' | ')} |\n`
  const rows = token.rows
    .map((row) => `| ${row.map((t) => t.text).join(' | ')} |`)
    .join('\n')
  return header + alignRow + rows
}

/** 分段计算: 保护公式 → lexer → 逐 token 归类 */
const segments = computed<Segment[]>(() => {
  const { text: protectedContent, mathMap } = protectMath(props.content)
  const tokens = marked.lexer(protectedContent)
  const result: Segment[] = []
  let idx = 0
  let currentTextTokens: Tokens.Generic[] = []

  // 把累计的普通 token 渲染为 HTML 文本段
  const flushText = () => {
    if (currentTextTokens.length > 0) {
      const html = marked.parser(currentTextTokens)
      result.push({
        type: 'text',
        content: restoreMathHtml(html, mathMap),
        id: `${props.blockId}-${idx++}`,
      })
      currentTextTokens = []
    }
  }

  for (const token of tokens) {
    if (token.type === 'code' && token.lang === 'mermaid') {
      flushText()
      result.push({
        type: 'mermaid',
        content: token.text,
        code: token.text,
        id: `${props.blockId}-${idx++}`,
      })
    } else if (token.type === 'table') {
      flushText()
      const rawMd = buildTableMarkdown(token as Tokens.Table)
      result.push({
        type: 'table',
        content: restoreMathHtml(rawMd, mathMap),
        id: `${props.blockId}-${idx++}`,
      })
    } else {
      currentTextTokens.push(token)
    }
  }
  flushText()
  return result
})

/** mermaid 源码被编辑(向上冒泡, 供页面回写消息内容) */
const handleMermaidUpdate = (payload: { id: string; code: string }) => {
  emit('update:mermaid-code', payload)
}
</script>

<template>
  <div class="md-rich">
    <template v-for="seg in segments" :key="seg.id">
      <!-- 文本段: 已是 HTML(含 katex 恢复), 直接渲染 -->
      <div v-if="seg.type === 'text'" class="markdown-body" v-html="seg.content" />

      <!-- 表格段 -->
      <TableBlock v-else-if="seg.type === 'table'" :markdown="seg.content" :block-id="seg.id" />

      <!-- mermaid 图表段 -->
      <MermaidBlock
        v-else
        :code="seg.code ?? seg.content"
        :block-id="seg.id"
        @update:code="(code: string) => handleMermaidUpdate({ id: seg.id, code })"
      />
    </template>
  </div>
</template>

<style scoped>
.md-rich {
  font-size: 0.9rem;
  line-height: 1.75;
  color: var(--el-text-color-primary, #2b3a30);
  word-break: break-word;
}

.md-rich :deep(> :first-child) {
  margin-top: 0;
}

.md-rich :deep(> :last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(p) {
  margin: 0.5em 0;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4) {
  margin: 1em 0 0.4em;
  font-weight: 600;
  color: var(--el-text-color-primary, #2b3a30);
}

.markdown-body :deep(h1) { font-size: 1.25rem; }
.markdown-body :deep(h2) { font-size: 1.15rem; }
.markdown-body :deep(h3) { font-size: 1.05rem; }

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 1.25em;
  margin: 0.5em 0;
}

.markdown-body :deep(li) {
  margin: 0.25em 0;
}

.markdown-body :deep(li > p) {
  margin: 0;
}

.markdown-body :deep(a) {
  color: var(--note-green, #6cbf8f);
  text-decoration: none;
  border-bottom: 1px dashed var(--note-green, #6cbf8f);
}

.markdown-body :deep(blockquote) {
  margin: 0.6em 0;
  padding: 0.2em 0 0.2em 0.9em;
  border-left: 3px solid var(--note-green, #6cbf8f);
  border-radius: 2px;
  color: var(--el-text-color-secondary, #6b7f6e);
}

/* 行内代码: 苔绿胶囊 */
.markdown-body :deep(code) {
  background: var(--note-tint, #e7f3e9);
  border-radius: 4px;
  padding: 0.15em 0.4em;
  font-size: 0.85em;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  color: var(--note-green-deep, #3f7a52);
}

/* 代码块: 深绿纸面 */
.markdown-body :deep(pre) {
  background: var(--note-soft, #f2f7f0);
  border: 1px solid var(--note-border, #e2e8e3);
  border-radius: 10px;
  padding: 0.9em 1em;
  overflow-x: auto;
  margin: 0.7em 0;
}

.markdown-body :deep(pre code) {
  background: none;
  padding: 0;
  color: var(--el-text-color-primary, #2b3a30);
  font-size: 0.85em;
  line-height: 1.6;
}

.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid var(--note-border, #e2e8e3);
  margin: 1em 0;
}

.markdown-body :deep(img) {
  max-width: 100%;
  border-radius: 8px;
}

/* katex 块级公式滚动容器(超宽公式不撑破布局) */
.markdown-body :deep(.katex-display) {
  overflow-x: auto;
  overflow-y: hidden;
  padding: 4px 0;
}
</style>
