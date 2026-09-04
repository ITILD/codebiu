// src/utils/export.ts
// 消息内容导出工具集: 剪贴板 / 表格导出 Excel / Markdown 导出 Word / PDF / SVG 转 PNG
import ExcelJS from 'exceljs'
import { saveAs } from 'file-saver'
import { marked } from 'marked'

/* ============ 剪贴板 ============ */

/**
 * 复制文本到剪贴板
 * 优先 navigator.clipboard, 非安全上下文回退到 textarea + execCommand
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    // 进入兜底方案
  }
  try {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.position = 'fixed'
    textarea.style.top = '-9999px'
    textarea.style.left = '-9999px'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.focus()
    textarea.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(textarea)
    return ok
  } catch {
    return false
  }
}

/* ============ 下载触发 ============ */

/** 通过 <a download> 触发文件下载(必须挂载到 DOM 才能全浏览器兼容) */
export function triggerDownload(href: string, fileName: string): void {
  const link = document.createElement('a')
  link.href = href
  link.download = fileName
  link.target = '_self'
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  // 留一帧时间发起下载后清理节点
  setTimeout(() => {
    if (link.parentNode) document.body.removeChild(link)
  }, 150)
}

/** 触发 Blob 下载(自动管理 object URL 生命周期) */
export function triggerBlobDownload(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob)
  triggerDownload(url, fileName)
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/* ============ 表格导出 ============ */

/** 从 HTML 表格元素提取数据导出为 .xlsx(表头加粗 + 自适应列宽) */
export async function exportTableToExcel(
  tableEl: HTMLTableElement,
  fileName = 'table',
): Promise<void> {
  const workbook = new ExcelJS.Workbook()
  const worksheet = workbook.addWorksheet('Sheet1')

  const rows = tableEl.querySelectorAll('tr')
  rows.forEach((row, rowIdx) => {
    const cells = row.querySelectorAll('th, td')
    const excelRow = worksheet.getRow(rowIdx + 1)
    cells.forEach((cell, colIdx) => {
      const cellValue = excelRow.getCell(colIdx + 1)
      cellValue.value = cell.textContent?.trim() ?? ''
      if (rowIdx === 0) cellValue.font = { bold: true }
    })
  })

  // 按内容长度自适应列宽(上限60)
  const colCount = worksheet.columnCount
  for (let c = 1; c <= colCount; c++) {
    let maxLen = 10
    const rowCount = worksheet.rowCount
    for (let r = 1; r <= rowCount; r++) {
      const val = worksheet.getRow(r).getCell(c).value
      const len = String(val ?? '').length
      if (len > maxLen) maxLen = len
    }
    worksheet.getColumn(c).width = Math.min(maxLen + 4, 60)
  }

  const buffer = await workbook.xlsx.writeBuffer()
  const blob = new Blob([buffer], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
  saveAs(blob, `${fileName}.xlsx`)
}

/** HTML 表格 → Markdown 表格文本(管道符转义) */
export function tableToMarkdown(tableEl: HTMLTableElement): string {
  const rows = tableEl.querySelectorAll('tr')
  const lines: string[] = []
  rows.forEach((row, rowIdx) => {
    const cells = row.querySelectorAll('th, td')
    const cellTexts = Array.from(cells).map((c) =>
      (c.textContent ?? '').trim().replace(/\|/g, '\\|').replace(/\n/g, ' '),
    )
    lines.push(`| ${cellTexts.join(' | ')} |`)
    if (rowIdx === 0) {
      lines.push(`| ${cellTexts.map(() => '---').join(' | ')} |`)
    }
  })
  return lines.join('\n')
}

/** HTML 表格 → TSV 文本(可直接粘贴进 Excel) */
export function tableToTSV(tableEl: HTMLTableElement): string {
  const rows = tableEl.querySelectorAll('tr')
  const lines: string[] = []
  rows.forEach((row) => {
    const cells = row.querySelectorAll('th, td')
    const cellTexts = Array.from(cells).map((c) =>
      (c.textContent ?? '').trim().replace(/\t/g, ' ').replace(/\n/g, ' '),
    )
    lines.push(cellTexts.join('\t'))
  })
  return lines.join('\n')
}

/* ============ SVG → PNG ============ */

/**
 * 读取 SVG 元素的真实渲染尺寸
 * 优先级: viewBox → width/height 属性 → getBBox → 临时去除 transform 的包围盒
 */
const getSvgRealSize = (
  svgEl: SVGSVGElement,
): { width: number; height: number } => {
  const vb = svgEl.viewBox.baseVal
  if (vb && vb.width > 0 && vb.height > 0) {
    return { width: vb.width, height: vb.height }
  }
  const wAttr = svgEl.getAttribute('width')
  const hAttr = svgEl.getAttribute('height')
  const w = wAttr ? parseFloat(wAttr) : 0
  const h = hAttr ? parseFloat(hAttr) : 0
  if (w > 0 && h > 0 && !wAttr?.endsWith('%') && !hAttr?.endsWith('%')) {
    return { width: w, height: h }
  }
  try {
    const bbox = svgEl.getBBox()
    if (bbox.width > 0 && bbox.height > 0) {
      return { width: bbox.width, height: bbox.height }
    }
  } catch {
    // 忽略, 走兜底
  }
  const parent = svgEl.parentElement
  const prevTransform = parent?.style.transform ?? ''
  if (parent) parent.style.transform = 'none'
  const rect = svgEl.getBoundingClientRect()
  if (parent) parent.style.transform = prevTransform
  return { width: rect.width || 400, height: rect.height || 300 }
}

/**
 * SVG 元素转 PNG data URL(先转 base64 data URL 加载 Image, 避免跨域污染画布)
 */
export function svgElementToPngDataUrl(
  svgEl: SVGSVGElement,
  width: number,
  height: number,
  scale = 2,
): Promise<string> {
  return new Promise((resolve, reject) => {
    try {
      const svgClone = svgEl.cloneNode(true) as SVGSVGElement
      svgClone.removeAttribute('style')
      svgClone.setAttribute('width', String(width))
      svgClone.setAttribute('height', String(height))
      if (!svgClone.getAttribute('viewBox')) {
        svgClone.setAttribute('viewBox', `0 0 ${width} ${height}`)
      }
      svgClone.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
      svgClone.setAttribute('xmlns:xlink', 'http://www.w3.org/1999/xlink')

      const svgData = new XMLSerializer().serializeToString(svgClone)
      const svgBase64 = btoa(unescape(encodeURIComponent(svgData)))
      const dataUrl = `data:image/svg+xml;base64,${svgBase64}`

      const img = new Image()
      img.onload = () => {
        try {
          const canvas = document.createElement('canvas')
          canvas.width = Math.max(1, Math.floor(width * scale))
          canvas.height = Math.max(1, Math.floor(height * scale))
          const ctx = canvas.getContext('2d')
          if (!ctx) {
            reject(new Error('画布初始化失败'))
            return
          }
          ctx.fillStyle = '#fff'
          ctx.fillRect(0, 0, canvas.width, canvas.height)
          ctx.scale(scale, scale)
          ctx.drawImage(img, 0, 0, width, height)
          resolve(canvas.toDataURL('image/png'))
        } catch (e) {
          reject(e instanceof Error ? e : new Error(String(e)))
        }
      }
      img.onerror = () => reject(new Error('SVG 加载失败(可能存在外部资源引用)'))
      img.src = dataUrl
    } catch (e) {
      reject(e instanceof Error ? e : new Error(String(e)))
    }
  })
}

/* ============ Markdown 导出 Word / PDF ============ */

/** 清理 marked 输出 HTML 中的空段落/空列表项, 避免导出 Word 出现空行 */
function cleanupHtmlForWord(html: string): string {
  let result = html.replace(/<p>\s*<\/p>/gi, '')
  result = result.replace(/<p>\s*<br\s*\/?>\s*<\/p>/gi, '')
  result = result.replace(/<li>\s*<\/li>/gi, '')
  result = result.replace(/<div>\s*<\/div>/gi, '')
  result = result.replace(/<h[1-6]>\s*<\/h[1-6]>/gi, '')
  result = result.replace(/(<br\s*\/?>\s*){2,}/gi, '<br/>')
  result = result.replace(/\n\s*\n\s*\n/g, '\n\n')
  return result
}

/** mermaid 按需异步加载(约 1MB, 避免静态打包进主包) */
let mermaidModule: typeof import('mermaid')['default'] | null = null
const ensureMermaidInit = async () => {
  if (!mermaidModule) {
    mermaidModule = (await import('mermaid')).default
    mermaidModule.initialize({
      startOnLoad: false,
      theme: 'default',
      securityLevel: 'loose',
    })
  }
  return mermaidModule
}

/** 将 markdown 中所有 ```mermaid 代码块渲染为 PNG(用于导出时嵌入) */
async function renderMermaidBlocksToImages(
  markdownText: string,
  prefix: string,
): Promise<{ placeholder: string; dataUrl: string }[]> {
  const mermaidRegex = /```mermaid\s*\n([\s\S]*?)```/g
  const matches: { placeholder: string; code: string }[] = []
  let m: RegExpExecArray | null
  let idx = 0
  while ((m = mermaidRegex.exec(markdownText)) !== null) {
    // 占位符不能以 __ 包裹, 否则会被 marked 解析为 <strong> 导致替换失效
    matches.push({ placeholder: `${prefix}IMG${idx}`, code: m[1].trim() })
    idx++
  }
  if (matches.length === 0) return []

  const result: { placeholder: string; dataUrl: string }[] = []
  let mermaid: Awaited<ReturnType<typeof ensureMermaidInit>>
  try {
    mermaid = await ensureMermaidInit()
  } catch (e) {
    console.warn('[export] mermaid 初始化失败:', e)
    return []
  }

  // mermaid.render 需要挂载在 DOM 上的临时容器
  const host = document.createElement('div')
  host.style.position = 'absolute'
  host.style.top = '-99999px'
  host.style.left = '-99999px'
  host.style.width = '800px'
  host.style.visibility = 'hidden'
  document.body.appendChild(host)

  try {
    for (const { placeholder, code } of matches) {
      try {
        const renderId = `${prefix.toLowerCase()}-${placeholder}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
        host.innerHTML = ''
        const { svg } = await mermaid.render(renderId, code)
        const tmp = document.createElement('div')
        tmp.innerHTML = svg
        const svgEl = tmp.querySelector('svg') as SVGSVGElement | null
        if (!svgEl) continue

        const { width, height } = getSvgRealSize(svgEl)
        // A4 单页可用区域约束: 按宽/高双向缩放取小
        const maxW = 500
        const maxH = 750
        let finalW = width
        let finalH = height
        if (finalW > maxW) {
          finalH = (finalH * maxW) / finalW
          finalW = maxW
        }
        if (finalH > maxH) {
          finalW = (finalW * maxH) / finalH
          finalH = maxH
        }
        const dataUrl = await svgElementToPngDataUrl(svgEl, finalW, finalH, 2)
        result.push({ placeholder, dataUrl })
      } catch (e) {
        console.warn(`[export] mermaid 渲染失败 (${placeholder}):`, e)
      }
    }
  } finally {
    document.body.removeChild(host)
  }
  return result
}

/** 将 mermaid 代码块替换为占位符(避免被 marked 解析为代码块) */
function replaceMermaidWithPlaceholders(markdownText: string, prefix: string): string {
  const mermaidRegex = /```mermaid\s*\n([\s\S]*?)```/g
  let idx = 0
  return markdownText.replace(mermaidRegex, () => {
    const placeholder = `${prefix}IMG${idx}`
    idx++
    return `\n\n${placeholder}\n\n`
  })
}

/** 将 HTML 中的占位符替换回 <img> */
function applyMermaidImages(
  html: string,
  images: { placeholder: string; dataUrl: string }[],
): string {
  let result = html
  for (const { placeholder, dataUrl } of images) {
    const imgTag = `<img src="${dataUrl}" style="max-width:100%;height:auto;" />`
    result = result.replace(
      new RegExp(`<p>\\s*${placeholder}\\s*</p>`, 'g'),
      `<p style="text-align:center;">${imgTag}</p>`,
    )
    result = result.replace(placeholder, imgTag)
  }
  return result
}

/**
 * Markdown 导出为 Word(.doc)
 * - mermaid 代码块渲染为 PNG 嵌入
 * - 清理空段落, 包装为 Word 兼容 HTML
 */
export async function exportMarkdownToDocx(
  markdownText: string,
  fileName = 'document',
): Promise<void> {
  const images = await renderMermaidBlocksToImages(markdownText, 'MERMAID_DOCX')
  const processedMd = replaceMermaidWithPlaceholders(markdownText, 'MERMAID_DOCX')

  let htmlBody = marked.parse(processedMd, { async: false }) as string
  htmlBody = cleanupHtmlForWord(htmlBody)
  htmlBody = applyMermaidImages(htmlBody, images)

  const fullHtml = `<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40">
<head>
<meta charset="utf-8" />
<meta name="ProgId" content="Word.Document">
<meta name="Generator" content="Microsoft Word 15">
<meta name="Originator" content="Microsoft Word 15">
<title>${fileName}</title>
<!--[if gte mso 9]><xml><w:WordDocument><w:View>Print</w:View><w:Zoom>100</w:Zoom><w:DoNotOptimizeForBrowser/></w:WordDocument></xml><![endif]-->
<style>
@page { size: A4; margin: 2.5cm; }
body { font-family: '微软雅黑', Arial, sans-serif; font-size: 12pt; line-height: 1.6; }
h1 { font-size: 20pt; margin: 16pt 0 8pt; }
h2 { font-size: 16pt; margin: 14pt 0 6pt; }
h3 { font-size: 14pt; margin: 12pt 0 4pt; }
p { margin: 6pt 0; }
ul, ol { margin: 6pt 0; padding-left: 24pt; }
li { margin: 2pt 0; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0; }
th, td { border: 1px solid #000; padding: 6px; font-size: 11pt; }
th { background: #f0f0f0; font-weight: bold; }
pre { background: #f5f5f5; padding: 8px; border: 1px solid #ddd; font-family: 'Courier New', monospace; font-size: 10pt; }
code { font-family: 'Courier New', monospace; }
img { max-width: 100%; }
</style>
</head>
<body>
${htmlBody}
</body>
</html>`

  const blob = new Blob(['\ufeff', fullHtml], { type: 'application/msword' })
  triggerBlobDownload(blob, `${fileName}.doc`)
}

/**
 * 在 canvas 指定 y 坐标附近向上寻找空白行(全白像素行), PDF 分页时避免切断文字
 */
const findBlankLineNear = (
  ctx: CanvasRenderingContext2D,
  canvasWidth: number,
  canvasHeight: number,
  targetY: number,
  searchRange: number,
): number => {
  if (targetY <= 0 || targetY >= canvasHeight) return targetY
  const y0 = Math.max(0, targetY - searchRange)
  const y1 = Math.min(targetY, canvasHeight - 1)
  const regionHeight = y1 - y0 + 1
  if (regionHeight <= 0) return targetY
  try {
    const imageData = ctx.getImageData(0, y0, canvasWidth, regionHeight)
    const data = imageData.data
    // 从下往上找空白行
    for (let y = regionHeight - 1; y >= 0; y--) {
      let isBlank = true
      for (let x = 0; x < canvasWidth; x++) {
        const idx = (y * canvasWidth + x) * 4
        if (data[idx] < 250 || data[idx + 1] < 250 || data[idx + 2] < 250) {
          isBlank = false
          break
        }
      }
      if (isBlank) return y0 + y
    }
  } catch {
    // getImageData 失败时按原坐标切割
  }
  return targetY
}

/**
 * Markdown 导出为 PDF
 * - mermaid 渲染为 PNG 嵌入
 * - html2canvas 截图 + jsPDF 分页(空白行处切割)
 */
export async function exportMarkdownToPdf(
  markdownText: string,
  fileName = 'document',
): Promise<void> {
  const images = await renderMermaidBlocksToImages(markdownText, 'MERMAID_PDF')
  const processedMd = replaceMermaidWithPlaceholders(markdownText, 'MERMAID_PDF')

  let htmlBody = marked.parse(processedMd, { async: false }) as string
  htmlBody = cleanupHtmlForWord(htmlBody)
  htmlBody = applyMermaidImages(htmlBody, images)

  // 离屏容器按 A4 宽度渲染
  const host = document.createElement('div')
  host.style.position = 'absolute'
  host.style.top = '-99999px'
  host.style.left = '-99999px'
  host.style.width = '794px' // A4 96dpi
  host.style.padding = '40px'
  host.style.background = '#ffffff'
  host.style.color = '#2b3a30'
  host.style.fontFamily = "'微软雅黑', Arial, sans-serif"
  host.style.fontSize = '14px'
  host.style.lineHeight = '1.7'
  host.innerHTML = htmlBody
  document.body.appendChild(host)

  try {
    // 等待图片加载完成
    const imgs = Array.from(host.querySelectorAll('img'))
    await Promise.all(
      imgs.map((img) => {
        if (img.complete) return Promise.resolve()
        return new Promise<void>((resolve) => {
          img.onload = () => resolve()
          img.onerror = () => resolve()
        })
      }),
    )

    const { default: html2canvas } = await import('html2canvas')
    const canvas = await html2canvas(host, {
      scale: 2,
      backgroundColor: '#ffffff',
      useCORS: true,
      logging: false,
    })

    const { jsPDF } = await import('jspdf')
    const pdf = new jsPDF('p', 'mm', 'a4')
    const pdfWidth = pdf.internal.pageSize.getWidth()
    const pdfHeight = pdf.internal.pageSize.getHeight()
    const margin = 10 // mm
    const usablePdfHeight = pdfHeight - margin * 2
    const pxPerMm = canvas.width / pdfWidth
    const pageCanvasHeight = Math.floor(usablePdfHeight * pxPerMm)

    if (canvas.height <= pageCanvasHeight) {
      // 单页内容
      const imgData = canvas.toDataURL('image/png')
      const imgHeight = (canvas.height * pdfWidth) / canvas.width
      pdf.addImage(imgData, 'PNG', 0, margin, pdfWidth, imgHeight)
    } else {
      // 多页: 在空白行处切割
      const sourceCtx = canvas.getContext('2d')
      let position = 0
      let isFirstPage = true

      while (position < canvas.height) {
        let pageEnd = position + pageCanvasHeight
        if (pageEnd >= canvas.height) {
          pageEnd = canvas.height
        } else if (sourceCtx) {
          const blankY = findBlankLineNear(
            sourceCtx,
            canvas.width,
            canvas.height,
            pageEnd,
            50,
          )
          if (blankY > position) pageEnd = blankY
        }

        const pageHeight = pageEnd - position
        if (pageHeight <= 0) break

        const pageCanvas = document.createElement('canvas')
        pageCanvas.width = canvas.width
        pageCanvas.height = pageHeight
        const pageCtx = pageCanvas.getContext('2d')
        if (!pageCtx) break
        pageCtx.fillStyle = '#ffffff'
        pageCtx.fillRect(0, 0, pageCanvas.width, pageCanvas.height)
        pageCtx.drawImage(
          canvas,
          0, position,
          canvas.width, pageHeight,
          0, 0,
          canvas.width, pageHeight,
        )
        const pageData = pageCanvas.toDataURL('image/png')
        const pageImgHeight = (pageHeight * pdfWidth) / canvas.width

        if (!isFirstPage) pdf.addPage()
        pdf.addImage(pageData, 'PNG', 0, margin, pdfWidth, pageImgHeight)

        position = pageEnd
        isFirstPage = false
      }
    }

    pdf.save(`${fileName}.pdf`)
  } finally {
    document.body.removeChild(host)
  }
}
