<script setup lang="ts">
// Mermaid 图表渲染区块: 防抖串行渲染 + 缩放拖拽 + 导出PNG/复制/编辑源码
// 渲染使用离屏容器, 避免临时 SVG 挂到 body 引起页面闪烁
import {
  Camera, CopyDocument, ZoomIn, ZoomOut, Check, Close, FullScreen, Aim, EditPen,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { copyToClipboard, svgElementToPngDataUrl, triggerDownload } from '@/utils/export'

// mermaid 按需异步加载(约 1MB, 避免打包进聊天主包)
let mermaidModule: typeof import('mermaid')['default'] | null = null
const ensureMermaid = async () => {
  if (!mermaidModule) {
    mermaidModule = (await import('mermaid')).default
    mermaidModule.initialize({
      startOnLoad: false,
      theme: 'default',
      securityLevel: 'loose',
      themeVariables: {
        // 显式字体族, 避免系统回退字体导致的渲染发虚
        fontFamily:
          'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
      },
    })
  }
  return mermaidModule
}

interface Props {
  /** mermaid 源码 */
  code: string
  /** 区块唯一ID(渲染ID/导出文件名) */
  blockId: string
}

const props = defineProps<Props>()
const emit = defineEmits<{ (e: 'update:code', code: string): void }>()

// ===== DOM 引用 =====
const containerRef = ref<HTMLDivElement>()   // 图表显示容器
const wrapperRef = ref<HTMLDivElement>()     // 缩放/拖拽画布
const offscreenRef = ref<HTMLDivElement>()   // 离屏渲染容器

// ===== 状态 =====
const renderError = ref('')
const scale = ref(1)
const tx = ref(0)
const ty = ref(0)
const dragging = ref(false)
const editing = ref(false)
const editCode = ref('')
const currentCode = ref(props.code)

// ===== mermaid 模块级初始化(仅一次, 异步) =====

const raf = () => new Promise<void>((r) => requestAnimationFrame(() => r()))

/** 读取 SVG 实际尺寸 [w, h](viewBox 优先) */
const getSvgSize = (): [number, number] => {
  const svg = containerRef.value?.querySelector('svg')
  if (!svg) return [0, 0]
  const vb = svg.viewBox?.baseVal
  if (vb && vb.width > 0 && vb.height > 0) return [vb.width, vb.height]
  const w = parseFloat(svg.getAttribute('width') || '0')
  const h = parseFloat(svg.getAttribute('height') || '0')
  if (w > 0 && h > 0) return [w, h]
  return [400, 300]
}

// 首行是否匹配已知图表类型(避免半截代码反复报错)
const DIAGRAM_RE =
  /^(graph|flowchart|sequence|class|state|er|gantt|pie|journey|gitgraph|mindmap|timeline|quadrantchart|sankey|xychart|block|packet|kanban)/i
const looksRenderable = (code: string) =>
  code.trim().includes('\n') && DIAGRAM_RE.test(code.trim())

/* ===== 串行渲染 + 脏标记(流式输出时高频触发也不重入) ===== */
let rendering = false
let dirty = false
let disposed = false
let hasRendered = false
let lastChangeTime = 0
let debounceTimer: ReturnType<typeof setTimeout> | null = null

const isCodeChanging = () => Date.now() - lastChangeTime < 1200

/** 图表是否超出可视范围(用于判断是否需要重新自适应) */
const isOutOfBounds = () => {
  const el = wrapperRef.value
  if (!el) return false
  const [w, h] = getSvgSize()
  return (
    w > 0 &&
    (tx.value + w * scale.value > el.clientWidth + 16 ||
      ty.value + h * scale.value > el.clientHeight + 16)
  )
}

/** 自适应画布(整数像素, 消除亚像素模糊) */
const fitToScreen = () => {
  const el = wrapperRef.value
  if (!el) {
    tx.value = ty.value = 0
    scale.value = 1
    return
  }
  const [w, h] = getSvgSize()
  const aw = el.clientWidth - 32
  const ah = el.clientHeight - 32
  if (w <= 0 || h <= 0 || aw <= 0 || ah <= 0) {
    tx.value = ty.value = 0
    scale.value = 1
    return
  }
  const s = Math.min(aw / w, ah / h, 1)
  scale.value = s
  tx.value = Math.round((aw - w * s) / 2 + 16)
  ty.value = Math.round((ah - h * s) / 2 + 16)
}

/** 执行一次渲染(mermaid.parse 校验 → render 出 SVG → 注入容器) */
const doRender = async () => {
  if (rendering || disposed) return
  rendering = true

  const code = currentCode.value.trim()
  if (!code || !looksRenderable(code)) {
    rendering = false
    return
  }

  const id = `mm-${props.blockId}-${Date.now()}`
  try {
    const mermaid = await ensureMermaid()
    await mermaid.parse(code)
    const { svg } = await mermaid.render(id, code, offscreenRef.value)
    if (disposed || !containerRef.value) return

    renderError.value = ''
    containerRef.value.innerHTML = svg

    const el = containerRef.value.querySelector('svg')
    if (el) {
      const [w, h] = getSvgSize()
      el.style.cssText = 'max-width:none;width:auto;height:auto'
      // 写入 DOM 的宽高取整, 辅助浏览器正确计算比例
      el.setAttribute('width', `${Math.round(w)}`)
      el.setAttribute('height', `${Math.round(h)}`)
    }

    await raf()
    if (disposed) return
    // 首次渲染/代码稳定后/超出边界时自适应
    if (!hasRendered || !isCodeChanging() || isOutOfBounds()) fitToScreen()
    hasRendered = true
  } catch (e) {
    if (offscreenRef.value) offscreenRef.value.innerHTML = ''
    if (!disposed && !isCodeChanging())
      renderError.value = e instanceof Error ? e.message : String(e)
  } finally {
    rendering = false
    if (dirty && !disposed) {
      dirty = false
      doRender()
    }
  }
}

/** 防抖调度(流式期间 33ms 合并一次) */
const scheduleRender = () => {
  lastChangeTime = Date.now()
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    if (rendering) dirty = true
    else doRender()
  }, 33)
}

onMounted(doRender)
watch(currentCode, scheduleRender)
watch(() => props.code, (v) => { currentCode.value = v })
watch(editing, (v) => { if (!v) nextTick(doRender) })
onBeforeUnmount(() => {
  disposed = true
  if (debounceTimer) clearTimeout(debounceTimer)
})

/* ===== 缩放 & 拖拽 ===== */
const transformStyle = computed(() => ({
  transform: `translate(${tx.value}px,${ty.value}px) scale(${scale.value})`,
  transformOrigin: '0 0',
  transition: dragging.value ? 'none' : 'transform .35s cubic-bezier(.4,0,.2,1)',
}))

/** 以 (cx,cy) 为锚点缩放到 s(整数像素, 防字体发虚) */
const zoomAt = (cx: number, cy: number, s: number) => {
  const c = Math.min(Math.max(s, 0.1), 8)
  const r = c / scale.value
  tx.value = Math.round(cx - (cx - tx.value) * r)
  ty.value = Math.round(cy - (cy - ty.value) * r)
  scale.value = c
}

const zoomBy = (f: number) => {
  const r = wrapperRef.value?.getBoundingClientRect()
  if (r) zoomAt(r.width / 2, r.height / 2, scale.value * f)
}

const onWheel = (e: WheelEvent) => {
  if (!wrapperRef.value) return
  e.preventDefault()
  const r = wrapperRef.value.getBoundingClientRect()
  zoomAt(e.clientX - r.left, e.clientY - r.top, scale.value * (e.deltaY < 0 ? 1.1 : 1 / 1.1))
}

let sx = 0, sy = 0, stx = 0, sty = 0
const onPointerDown = (e: PointerEvent) => {
  if (e.button !== 0) return
  dragging.value = true
  sx = e.clientX
  sy = e.clientY
  stx = tx.value
  sty = ty.value
  ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
}
const onPointerMove = (e: PointerEvent) => {
  if (dragging.value) {
    tx.value = Math.round(stx + e.clientX - sx)
    ty.value = Math.round(sty + e.clientY - sy)
  }
}
const onPointerUp = () => { dragging.value = false }

/* ===== 工具栏操作 ===== */
const fullscreen = ref(false)
const toggleFullscreen = async () => {
  fullscreen.value = !fullscreen.value
  if (fullscreen.value) {
    await nextTick()
    await raf()
    fitToScreen()
  }
}

const handleCopy = async () => {
  if (await copyToClipboard(currentCode.value)) ElMessage.success('已复制源码')
  else ElMessage.error('复制失败')
}

/** 导出 PNG(2x 高清) */
const exportPng = async () => {
  const svg = containerRef.value?.querySelector('svg')
  if (!svg) {
    ElMessage.warning('暂无可导出的图表')
    return
  }
  try {
    const [w, h] = getSvgSize()
    triggerDownload(await svgElementToPngDataUrl(svg, w, h, 2), `mermaid-${props.blockId}.png`)
    ElMessage.success('图片已导出')
  } catch (e) {
    ElMessage.error('导出失败: ' + (e instanceof Error ? e.message : '未知错误'))
  }
}

/* ===== 编辑源码 ===== */
const startEdit = () => {
  editCode.value = currentCode.value
  editing.value = true
}
const commitEdit = () => {
  currentCode.value = editCode.value
  emit('update:code', editCode.value)
  editing.value = false
  ElMessage.success('已更新图表')
}
const cancelEdit = () => { editing.value = false }
</script>

<template>
  <div class="mm-block" :class="{ 'is-fullscreen': fullscreen }">
    <!-- 工具栏 -->
    <div class="mm-head">
      <span class="mm-title">流程图</span>
      <div class="mm-tools">
        <template v-if="editing">
          <el-tooltip content="确认" placement="top">
            <button class="mm-btn primary" @click="commitEdit"><el-icon><Check /></el-icon></button>
          </el-tooltip>
          <el-tooltip content="取消" placement="top">
            <button class="mm-btn" @click="cancelEdit"><el-icon><Close /></el-icon></button>
          </el-tooltip>
        </template>
        <template v-else>
          <el-tooltip content="导出图片" placement="top">
            <button class="mm-btn" @click="exportPng"><el-icon><Camera /></el-icon></button>
          </el-tooltip>
          <el-tooltip content="复制源码" placement="top">
            <button class="mm-btn" @click="handleCopy"><el-icon><CopyDocument /></el-icon></button>
          </el-tooltip>
          <el-tooltip content="编辑源码" placement="top">
            <button class="mm-btn" @click="startEdit"><el-icon><EditPen /></el-icon></button>
          </el-tooltip>
          <el-tooltip content="自适应" placement="top">
            <button class="mm-btn" @click="fitToScreen"><el-icon><Aim /></el-icon></button>
          </el-tooltip>
          <el-tooltip content="放大" placement="top">
            <button class="mm-btn" @click="zoomBy(1.2)"><el-icon><ZoomIn /></el-icon></button>
          </el-tooltip>
          <el-tooltip content="缩小" placement="top">
            <button class="mm-btn" @click="zoomBy(1 / 1.2)"><el-icon><ZoomOut /></el-icon></button>
          </el-tooltip>
          <el-tooltip :content="fullscreen ? '退出全屏' : '全屏'" placement="top">
            <button class="mm-btn" :class="{ active: fullscreen }" @click="toggleFullscreen">
              <el-icon><FullScreen /></el-icon>
            </button>
          </el-tooltip>
        </template>
      </div>
    </div>

    <!-- 编辑态: 源码编辑 -->
    <div v-if="editing" class="mm-edit">
      <textarea v-model="editCode" class="mm-textarea" spellcheck="false" placeholder="请输入 mermaid 源码" />
    </div>

    <!-- 查看态: 画布(滚轮缩放 + 拖拽平移) -->
    <div
      v-else
      ref="wrapperRef"
      class="mm-canvas-wrap"
      :class="{ dragging }"
      @wheel="onWheel"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
    >
      <div ref="containerRef" class="mm-canvas" :style="transformStyle" />
    </div>

    <!-- 渲染错误提示 -->
    <div v-if="renderError && !editing" class="mm-error">
      图表格式错误: {{ renderError }}
    </div>

    <!-- 离屏渲染容器: mermaid 临时 DOM 仅在此, 不污染页面 -->
    <div ref="offscreenRef" class="mm-offscreen" aria-hidden="true" />
  </div>
</template>

<style scoped>
.mm-block {
  position: relative;
  margin: 12px 0;
  border: 1px solid var(--note-border, #e2e8e3);
  border-radius: 12px;
  overflow: hidden;
  background: var(--note-card, #fdfefc);
}

.mm-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  background: var(--note-soft, #f2f7f0);
  border-bottom: 1px solid var(--note-border, #e2e8e3);
}

.mm-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--note-green-deep, #3f7a52);
}

.mm-tools {
  display: flex;
  align-items: center;
  gap: 2px;
}

.mm-btn {
  min-width: 28px;
  height: 28px;
  padding: 0 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--note-sub, #6b7f6e);
  cursor: pointer;
  font-size: 14px;
  transition: all 0.15s;
}

.mm-btn:hover {
  background: var(--note-tint, #e7f3e9);
  color: var(--note-green, #6cbf8f);
}

.mm-btn.active,
.mm-btn.primary {
  background: var(--note-green, #6cbf8f);
  color: #fff;
}

.mm-canvas-wrap {
  position: relative;
  padding: 16px;
  overflow: hidden;
  min-height: 420px;
  max-height: 70vh;
  cursor: grab;
  user-select: none;
}

.mm-canvas-wrap.dragging {
  cursor: grabbing;
}

.mm-canvas {
  position: absolute;
  top: 0;
  left: 0;
  min-height: 80px;
  will-change: transform;
}

/* 增强字体与形状渲染质量 */
.mm-canvas :deep(svg) {
  display: block;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: optimizeLegibility;
  shape-rendering: geometricPrecision;
}

.mm-block.is-fullscreen {
  position: fixed;
  inset: 0;
  z-index: 9999;
  margin: 0;
  border-radius: 0;
  display: flex;
  flex-direction: column;
}

.mm-block.is-fullscreen .mm-canvas-wrap {
  flex: 1;
  max-height: none;
}

.mm-error {
  padding: 8px 12px;
  font-size: 12px;
  color: #c0453e;
  background: #fbf6f4;
}

.mm-edit {
  background: #10241a;
}

.mm-textarea {
  width: 100%;
  min-height: 280px;
  max-height: 500px;
  padding: 12px;
  border: none;
  outline: none;
  resize: vertical;
  box-sizing: border-box;
  font: 13px/1.6 ui-monospace, Consolas, monospace;
  color: #dcebe0;
  background: transparent;
}

.mm-offscreen {
  position: absolute;
  left: -9999px;
  top: -9999px;
  width: 0;
  height: 0;
  overflow: hidden;
  visibility: hidden;
  pointer-events: none;
}
</style>
