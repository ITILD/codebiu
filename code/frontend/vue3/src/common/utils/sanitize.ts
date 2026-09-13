/**
 * HTML 消毒工具(v-html 渲染前统一调用)
 *
 * 背景: marked 不做 HTML 消毒, LLM 输出/知识库文档/博客内容可能携带
 * <script>、on* 事件、javascript: 链接等恶意片段, 直接 v-html 会造成 XSS。
 * 所有"渲染不可信内容为 HTML"的场景必须先过 sanitizeHtml。
 */
import DOMPurify from 'dompurify'

// 允许 katex 输出的 MathML/SVG 标签与属性, 其余危险内容全部剔除
const purify = DOMPurify()

/** 消毒 HTML 片段(同步, 基于 DOMParser; SSR 环境返回原文) */
export const sanitizeHtml = (html: string): string => {
  if (typeof window === 'undefined') return html
  return purify.sanitize(html, {
    USE_PROFILES: { html: true, svg: true, svgFilters: true, mathMl: true },
    ADD_ATTR: ['target'],
  })
}
