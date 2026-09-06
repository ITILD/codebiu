<template>
  <!-- Markdown 渲染视图(基于 marked, 支持 mermaid 图表, 展示博客正文/编辑预览) -->
  <div ref="rootEl" class="markdown-view break-words" v-html="html" />
</template>

<script setup lang="ts">
import { marked } from 'marked'
import type { Tokens } from 'marked'
import { useDebounceFn } from '@vueuse/core'
import { SysSettingStore } from '@/common/stores/sys'

const props = defineProps<{
  /** markdown 源文本 */
  content: string
}>()

const sysSettingStore = SysSettingStore()

// ---------- marked: 拦截 mermaid 代码块为占位 div, 其余走默认渲染 ----------
/** HTML 转义(代码/图表源码占位用) */
const escapeHtml = (s: string) =>
  s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')

marked.use({
  renderer: {
    code(token: Tokens.Code): string {
      const lang = (token.lang ?? '').trim()
      // mermaid 块: 输出占位 div, 挂载后异步渲染为 SVG
      if (lang === 'mermaid') {
        return `<div class="mermaid-block">${escapeHtml(token.text)}</div>`
      }
      const langAttr = lang ? ` class="language-${escapeHtml(lang)}"` : ''
      return `<pre><code${langAttr}>${escapeHtml(token.text)}</code></pre>`
    },
  },
})

/** 渲染为 HTML(同步模式) */
const html = computed(
  () => marked.parse(props.content ?? '', { async: false }) as string
)

// ---------- mermaid 按需异步渲染(仅在内容含图表块时加载) ----------
const rootEl = ref<HTMLElement | null>(null)

type MermaidModule = typeof import('mermaid')
let mermaidPromise: Promise<MermaidModule> | null = null
let renderSeq = 0

/** 渲染所有未处理的 mermaid 块(失败保留可读源码并标红提示) */
async function renderMermaidBlocks() {
  const root = rootEl.value
  if (!root) return
  const pending = Array.from(
    root.querySelectorAll<HTMLElement>('.mermaid-block:not([data-rendered])'),
  )
  if (pending.length === 0) return

  try {
    mermaidPromise ??= import('mermaid')
    const { default: mermaid } = await mermaidPromise
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: 'strict',
      // 跟随站点暗色模式
      theme: sysSettingStore.sysStyle.theme.isDark ? 'dark' : 'default',
      fontFamily: 'inherit',
    })

    for (const block of pending) {
      // 源码存 dataset, 主题切换重渲时 v-html 已被 SVG 替换仍可取回
      const code = block.dataset.code ?? block.textContent ?? ''
      block.dataset.code = code
      try {
        const { svg } = await mermaid.render(
          `mmd-${Date.now().toString(36)}-${renderSeq++}`,
          code,
        )
        block.innerHTML = svg
      } catch {
        // 语法错误等: 保留源码文本, 样式标红
        block.classList.add('mermaid-failed')
        block.textContent = code
      }
      block.dataset.rendered = 'true'
    }
  } catch (error) {
    console.error('mermaid 加载失败:', error)
  }
}

// 内容变化 → 防抖渲染(编辑预览连续输入时避免频繁重渲图表)
const debouncedRender = useDebounceFn(renderMermaidBlocks, 350)

watch(
  html,
  () => {
    nextTick(debouncedRender)
  },
  { immediate: true },
)

// 暗色模式切换 → 清除标记重渲全部图表
watch(
  () => sysSettingStore.sysStyle.theme.isDark,
  () => {
    rootEl.value
      ?.querySelectorAll<HTMLElement>('.mermaid-block')
      .forEach((b) => delete b.dataset.rendered)
    renderMermaidBlocks()
  },
)
</script>

<style scoped>
/* ---------- 基础排版 ---------- */
.markdown-view {
  line-height: 1.8;
  color: var(--el-text-color-regular);
  font-size: 14px;
}
.markdown-view :deep(h1),
.markdown-view :deep(h2),
.markdown-view :deep(h3),
.markdown-view :deep(h4) {
  margin: 1.2em 0 0.5em;
  font-weight: 700;
  color: var(--el-text-color-primary);
}
.markdown-view :deep(h1) {
  font-size: 1.45em;
  border-bottom: 1px solid rgba(107, 158, 120, 0.25);
  padding-bottom: 0.3em;
}
.markdown-view :deep(h2) {
  font-size: 1.25em;
  border-bottom: 1px dashed rgba(107, 158, 120, 0.2);
  padding-bottom: 0.25em;
}
.markdown-view :deep(h3) { font-size: 1.1em; }
.markdown-view :deep(h4) { font-size: 1em; }
.markdown-view :deep(p) { margin: 0.55em 0; line-height: 1.85; }
.markdown-view :deep(ul),
.markdown-view :deep(ol) { padding-left: 1.5em; margin: 0.5em 0; }
.markdown-view :deep(ul) { list-style: disc; }
.markdown-view :deep(ol) { list-style: decimal; }
.markdown-view :deep(li) { margin: 0.25em 0; }
.markdown-view :deep(li > ul),
.markdown-view :deep(li > ol) { margin: 0.25em 0; }

/* ---------- 引用块 ---------- */
.markdown-view :deep(blockquote) {
  margin: 0.7em 0;
  padding: 0.5em 1em;
  border-left: 3px solid rgba(107, 158, 120, 0.6);
  background: rgba(107, 158, 120, 0.08);
  border-radius: 0 8px 8px 0;
  color: var(--el-text-color-regular);
}
.markdown-view :deep(blockquote p) { margin: 0.2em 0; }

/* ---------- 代码(行内/块) ---------- */
.markdown-view :deep(code) {
  padding: 0.15em 0.4em;
  border-radius: 5px;
  background: rgba(107, 158, 120, 0.12);
  font-size: 0.88em;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
.markdown-view :deep(pre) {
  margin: 0.7em 0;
  padding: 0.85em 1em;
  border-radius: 10px;
  background: #f4f8f2;
  border: 1px solid rgba(107, 158, 120, 0.18);
  overflow-x: auto;
  font-size: 0.88em;
}
.markdown-view :deep(pre code) {
  padding: 0;
  background: transparent;
  border-radius: 0;
  font-size: 1em;
}

/* ---------- 链接/图片/分割线 ---------- */
.markdown-view :deep(a) {
  color: var(--el-color-primary);
  text-decoration: none;
}
.markdown-view :deep(a:hover) { text-decoration: underline; }
.markdown-view :deep(img) {
  max-width: 100%;
  border-radius: 10px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
}
.markdown-view :deep(hr) {
  border: none;
  border-top: 1px dashed rgba(107, 158, 120, 0.4);
  margin: 1.2em 0;
}

/* ---------- 表格(圆角外框 + 表头底色) ---------- */
.markdown-view :deep(table) {
  border-collapse: separate;
  border-spacing: 0;
  margin: 0.7em 0;
  border: 1px solid rgba(107, 158, 120, 0.3);
  border-radius: 8px;
  overflow: hidden;
  max-width: 100%;
}
.markdown-view :deep(th),
.markdown-view :deep(td) {
  border-bottom: 1px solid rgba(107, 158, 120, 0.18);
  border-right: 1px solid rgba(107, 158, 120, 0.18);
  padding: 0.4em 0.8em;
}
.markdown-view :deep(th):last-child,
.markdown-view :deep(td):last-child { border-right: none; }
.markdown-view :deep(tr):last-child td { border-bottom: none; }
.markdown-view :deep(th) {
  background: rgba(107, 158, 120, 0.1);
  font-weight: 600;
}

/* ---------- 任务列表 ---------- */
.markdown-view :deep(input[type='checkbox']) {
  accent-color: var(--el-color-primary);
  margin-right: 0.3em;
}

/* ---------- mermaid 图表块 ---------- */
.markdown-view :deep(.mermaid-block) {
  display: flex;
  justify-content: center;
  margin: 0.8em 0;
  padding: 0.7em;
  background: rgba(107, 158, 120, 0.05);
  border: 1px solid rgba(107, 158, 120, 0.2);
  border-radius: 10px;
  overflow-x: auto;
}
.markdown-view :deep(.mermaid-block svg) {
  max-width: 100%;
  height: auto;
}
/* 渲染失败: 保留源码 + 红色虚线提示 */
.markdown-view :deep(.mermaid-block.mermaid-failed) {
  justify-content: flex-start;
  border: 1px dashed rgba(220, 38, 38, 0.45);
  background: rgba(220, 38, 38, 0.04);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  white-space: pre-wrap;
  color: #b91c1c;
}

/* ---------- 暗色适配(html.dark) ---------- */
.dark .markdown-view :deep(code) { background: rgba(79, 141, 103, 0.22); }
.dark .markdown-view :deep(pre) {
  background: #15231c;
  border-color: rgba(79, 141, 103, 0.28);
}
.dark .markdown-view :deep(h1) { border-bottom-color: rgba(79, 141, 103, 0.35); }
.dark .markdown-view :deep(h2) { border-bottom-color: rgba(79, 141, 103, 0.3); }
.dark .markdown-view :deep(blockquote) { background: rgba(79, 141, 103, 0.14); }
.dark .markdown-view :deep(table) { border-color: rgba(79, 141, 103, 0.4); }
.dark .markdown-view :deep(th),
.dark .markdown-view :deep(td) {
  border-color: rgba(79, 141, 103, 0.3);
}
.dark .markdown-view :deep(th) { background: rgba(79, 141, 103, 0.18); }
.dark .markdown-view :deep(.mermaid-block) {
  background: rgba(79, 141, 103, 0.1);
  border-color: rgba(79, 141, 103, 0.3);
}
.dark .markdown-view :deep(.mermaid-block.mermaid-failed) {
  border-color: rgba(248, 113, 113, 0.5);
  background: rgba(248, 113, 113, 0.08);
  color: #fca5a5;
}
</style>
