// src/common/utils/latex.ts
// 数学公式保护渲染工具: 在 markdown 解析前把 $..$ / $$..$$ 替换为占位符,
// 解析后再用 katex 渲染回 HTML, 避免 markdown 语法与公式内容互相干扰
import katex from 'katex'

// 占位符格式: @@LATEX_序号@@ (不会与 markdown 语法冲突)
const PLACEHOLDER_PREFIX = '@@LATEX_'
const PLACEHOLDER_SUFFIX = '@@'
const BLOCK_MATH_REGEX = /\$\$([\s\S]+?)\$\$/g
const INLINE_MATH_REGEX = /\$([^\n$]+?)\$/g

/** 被保护的公式信息 */
interface ProtectedMath {
  latex: string
  displayMode: boolean
}

const escapeHtml = (str: string): string =>
  str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')

const buildPlaceholder = (index: number): string =>
  `${PLACEHOLDER_PREFIX}${index}${PLACEHOLDER_SUFFIX}`

/**
 * 保护文本中的公式: 替换为占位符并返回映射表
 * 块级公式 $$..$$ 优先, 行内 $..$ 做了防误判处理
 * (空内容/首尾空白/紧邻数字/跨行的 $ 均不视为公式)
 */
export const protectMath = (
  text: string,
): { text: string; mathMap: Map<string, ProtectedMath> } => {
  const mathMap = new Map<string, ProtectedMath>()
  let cursor = 0
  let result = ''

  const pushText = (s: string) => {
    result += s
  }

  const pushMath = (latex: string, displayMode: boolean) => {
    const key = buildPlaceholder(cursor++)
    mathMap.set(key, { latex: latex.trim(), displayMode })
    result += key
  }

  let i = 0
  const len = text.length
  while (i < len) {
    const ch = text[i]
    const next = text[i + 1]

    // 块级公式 $$...$$
    if (ch === '$' && next === '$') {
      const closeIdx = text.indexOf('$$', i + 2)
      if (closeIdx === -1) {
        pushText(text.slice(i))
        break
      }
      const content = text.slice(i + 2, closeIdx)
      if (content.length === 0) {
        pushText('$$$$')
        i = closeIdx + 2
        continue
      }
      pushMath(content, true)
      i = closeIdx + 2
      continue
    }

    // 行内公式 $...$(单行内闭合)
    if (ch === '$') {
      const lineEnd = text.indexOf('\n', i)
      const closeIdx = text.indexOf('$', i + 1)
      if (closeIdx === -1 || (lineEnd !== -1 && closeIdx > lineEnd)) {
        pushText(ch)
        i += 1
        continue
      }
      const content = text.slice(i + 1, closeIdx)
      if (
        content.length === 0 ||
        /\s/.test(content[0]) ||
        /\s/.test(content[content.length - 1])
      ) {
        pushText(ch)
        i += 1
        continue
      }
      // 前后紧邻数字视为货币符号(如 $100)
      if (i > 0 && /\d/.test(text[i - 1])) {
        pushText(ch)
        i += 1
        continue
      }
      if (/\d/.test(text[closeIdx + 1] ?? '')) {
        pushText(ch)
        i += 1
        continue
      }
      pushMath(content, false)
      i = closeIdx + 1
      continue
    }

    pushText(ch)
    i += 1
  }

  return { text: result, mathMap }
}

/**
 * 将 HTML 中的占位符恢复为 katex 渲染结果
 * 渲染失败时输出带错误提示的原始公式文本(不中断整体渲染)
 */
export const restoreMathHtml = (
  html: string,
  mathMap: Map<string, ProtectedMath>,
): string => {
  if (mathMap.size === 0) return html
  return html.replace(
    new RegExp(`${PLACEHOLDER_PREFIX}(\\d+)${PLACEHOLDER_SUFFIX}`, 'g'),
    (match, numStr: string) => {
      const key = buildPlaceholder(Number(numStr))
      const item = mathMap.get(key)
      if (!item) return match
      try {
        return katex.renderToString(item.latex, {
          throwOnError: false,
          displayMode: item.displayMode,
          strict: false,
          output: 'html',
        })
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err)
        // 失败时降级展示原始公式 + 错误说明
        return item.displayMode
          ? `<div class="katex-error" style="color:#c0453e;text-align:center;padding:8px 12px;border:1px dashed #e6b8b4;border-radius:6px;margin:8px 0;background:#fbf6f4;">${escapeHtml(`$$${item.latex}$$`)}<div style="font-size:12px;margin-top:4px;color:#c0453e;">${escapeHtml(message)}</div></div>`
          : `<span class="katex-error" style="color:#c0453e;background:#fbf6f4;padding:1px 4px;border-radius:4px;border:1px dashed #e6b8b4;" title="${escapeHtml(message)}">${escapeHtml(`$${item.latex}$`)}</span>`
      }
    },
  )
}

/** 便捷组合: 保护 → markdown 渲染 → 恢复公式 */
export const renderMarkdownWithLatex = (
  renderMarkdown: (text: string) => string,
  text: string,
): string => {
  const { text: protectedText, mathMap } = protectMath(text)
  const html = renderMarkdown(protectedText)
  return restoreMathHtml(html, mathMap)
}

export { BLOCK_MATH_REGEX, INLINE_MATH_REGEX }
