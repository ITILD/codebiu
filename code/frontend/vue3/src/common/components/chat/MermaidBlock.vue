<script lang="ts">
// 模块级(所有实例共享): 渲染守卫引用计数。
// 同页多个图并发渲染时, 先完成的实例不能把 html.mm-rendering 守卫提前撤掉
let guardCount = 0
</script>

<script setup lang="ts">
// Mermaid 图表渲染区块: 防抖串行渲染 + 缩放拖拽 + 导出PNG/复制/编辑源码
// 渲染使用离屏容器, 避免临时 SVG 挂到 body 引起页面闪烁
// 流式输出时按"稳定前缀"一段段渲染, 代码稳定后补一次全量渲染
import {
  Camera, CopyDocument, ZoomIn, ZoomOut, Check, Close, FullScreen, Aim, EditPen, Lock, Unlock,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { copyToClipboard, svgElementToPngDataUrl, triggerDownload } from '@/common/utils/export'

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
const offscreenRef = ref<HTMLDivElement>()   // 离屏渲染容器: 承接 mermaid 临时 DOM

// ===== 状态 =====
const renderError = ref('')
const busy = ref(false)          // 渲染进行中(流式跟随的"生成中"指示)
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
let lastRenderedCode = ''        // 上次实际渲染的代码(去重, 省流式期 CPU)
let debounceTimer: ReturnType<typeof setTimeout> | null = null
let stableTimer: ReturnType<typeof setTimeout> | null = null

const isCodeChanging = () => Date.now() - lastChangeTime < 1200

/** 流式结束后补一次全量渲染(流式截断丢掉的最后一行要渲出来) */
const scheduleStableRender = () => {
  if (stableTimer) clearTimeout(stableTimer)
  stableTimer = setTimeout(() => {
    stableTimer = null
    if (disposed) return
    // 正在渲染上一帧: 完成后由 dirty 机制自动接续
    if (rendering) dirty = true
    else doRender()
  }, 1500)
}

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
  // 全屏时允许放大铺满(矢量图放大不失真, 上限 4x 防小图过分放大), 普通模式最高 1:1
  const s = Math.min(aw / w, ah / h, fullscreen.value ? 4 : 1)
  scale.value = s
  tx.value = Math.round((aw - w * s) / 2 + 16)
  ty.value = Math.round((ah - h * s) / 2 + 16)
}

/** 执行一次渲染(流式中渲稳定前缀, 稳定后全量) */
const doRender = async () => {
  if (rendering || disposed) return
  rendering = true
  busy.value = true
  let guarded = false

  try {
    const full = currentCode.value.trim()
    if (!full || !looksRenderable(full)) return

    // 一段段生成: 流式中只渲染到上一个换行前的"稳定前缀"。
    // 正在写入的最后一行常是残缺语法, 直接渲染会报错闪烁;
    // 前缀始终语法完整, 图表随流式逐段长出, 稳定后由 trailing 渲染补全
    const streaming = isCodeChanging()
    const code = (streaming ? full.slice(0, full.lastIndexOf('\n') + 1) : full).trim()
    if (streaming) scheduleStableRender()
    if (!code || !looksRenderable(code) || code === lastRenderedCode) return
    lastRenderedCode = code

    const id = `mm-${props.blockId}-${Date.now()}`
    // 渲染期间挂起全局 reduced-motion 动画压缩(见 base.css 的 html.mm-rendering 豁免):
    // 动画时长被强压到 0.01ms 会破坏 mermaid 的文本测量, 导致布局间距爆炸、节点缩成小点
    if (++guardCount === 1) document.documentElement.classList.add('mm-rendering')
    guarded = true

    const mermaid = await ensureMermaid()
    await mermaid.parse(code)
    const { svg } = await mermaid.render(id, code, offscreenRef.value)
    if (disposed || !containerRef.value) return

    renderError.value = ''
    containerRef.value.innerHTML = svg

    const el = containerRef.value.querySelector('svg')
    if (el) {
      const [w, h] = getSvgSize()
      // 必须写显式像素尺寸: 内联样式优先级高于宽高属性,
      // 若用 auto, 浏览器会按容器百分比/默认尺寸解释 SVG 宽高, 导致显示大小不对
      el.style.cssText = `max-width:none;width:${Math.round(w)}px;height:${Math.round(h)}px`
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
    if (guarded && --guardCount === 0)
      document.documentElement.classList.remove('mm-rendering')
    busy.value = false
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

watch(currentCode, scheduleRender)
watch(() => props.code, (v) => { currentCode.value = v })
watch(editing, (v) => {
  if (!v) nextTick(() => {
    // 退出编辑后画布 DOM 重建, 重新挂尺寸监听(observe 对同一元素自动去重)
    if (wrapperRef.value) resizeObserver.observe(wrapperRef.value)
    doRender()
  })
})

/* ===== 缩放 & 拖拽 ===== */
// 交互锁定(默认锁定): 滚轮留给页面滚动, 避免浏览页面时误触缩放; 工具栏缩放/全屏仍可用
const locked = ref(true)
/** 切换锁定: 锁定时回到自适应位置, 解锁后自由缩放拖拽 */
const toggleLock = () => {
  locked.value = !locked.value
  if (locked.value) fitToScreen()
}

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
  // 锁定时不拦截滚轮, 事件自然冒泡交给页面滚动
  if (locked.value) return
  e.preventDefault()
  // 卸载瞬间 wrapper 可能已不存在, 判空防抖
  const r = wrapperRef.value?.getBoundingClientRect()
  if (!r) return
  zoomAt(e.clientX - r.left, e.clientY - r.top, scale.value * (e.deltaY < 0 ? 1.1 : 1 / 1.1))
}

let sx = 0, sy = 0, stx = 0, sty = 0
const onPointerDown = (e: PointerEvent) => {
  if (locked.value || e.button !== 0) return
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
  // 进入/退出全屏后容器尺寸都变了, 统一等 DOM 更新后重新自适应
  await nextTick()
  await raf()
  fitToScreen()
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

/* ===== 画布尺寸监听 + 生命周期 ===== */
// 全屏切换把区块从文档流切到 fixed, 布局完成时机可能晚于 nextTick+rAF
// (后台标签页下 rAF 甚至不会触发), 用 ResizeObserver 监听画布实际尺寸兜底,
// 确保全屏/窗口缩放后必然重新自适应
const resizeObserver = new ResizeObserver(() => {
  // 锁定态/全屏态: 尺寸变化自动重新自适应; 解锁态尊重用户手动缩放拖拽
  if (disposed || editing.value || (!locked.value && !fullscreen.value)) return
  fitToScreen()
})

onMounted(() => {
  // observe 首次会立即触发一次回调, 相当于挂载即自适应一轮
  if (wrapperRef.value) resizeObserver.observe(wrapperRef.value)
  doRender()
})

onBeforeUnmount(() => {
  disposed = true
  resizeObserver.disconnect()
  if (debounceTimer) clearTimeout(debounceTimer)
  if (stableTimer) clearTimeout(stableTimer)
})
</script>

<template>
  <!-- 样式已 UnoCSS 化: 静态原子类直接写, 状态分支(全屏/拖拽/锁定)走条件绑定,
       scoped 仅保留伪元素动画与 :deep SVG 渲染质量微调 -->
  <div
    class="relative my-3 overflow-hidden rounded-note-md bg-note-card shadow-note"
    :class="fullscreen ? 'fixed inset-0 z-9999 m-0 rounded-none flex flex-col' : ''"
  >
    <!-- 工具栏 -->
    <div class="flex items-center justify-between px-3 py-1.5 bg-note-soft">
      <div class="flex items-center gap-2">
        <span class="text-[13px] font-semibold text-note-green">流程图</span>
        <!-- 流式跟随渲染指示 -->
        <span v-if="busy" class="mm-live inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs text-note-green bg-note-tint">生成中…</span>
      </div>
      <div class="flex items-center gap-0.5">
        <template v-if="editing">
          <el-tooltip content="确认" placement="top">
            <button class="note-icon-btn bg-note-green text-white" @click="commitEdit"><el-icon><Check /></el-icon></button>
          </el-tooltip>
          <el-tooltip content="取消" placement="top">
            <button class="note-icon-btn" @click="cancelEdit"><el-icon><Close /></el-icon></button>
          </el-tooltip>
        </template>
        <template v-else>
          <el-tooltip :content="locked ? '解锁缩放拖拽' : '锁定并回到自适应'" placement="top">
            <button class="note-icon-btn" :class="!locked && 'bg-note-green text-white'" @click="toggleLock">
              <el-icon><Lock v-if="locked" /><Unlock v-else /></el-icon>
            </button>
          </el-tooltip>
          <el-tooltip content="导出图片" placement="top">
            <button class="note-icon-btn" @click="exportPng"><el-icon><Camera /></el-icon></button>
          </el-tooltip>
          <el-tooltip content="复制源码" placement="top">
            <button class="note-icon-btn" @click="handleCopy"><el-icon><CopyDocument /></el-icon></button>
          </el-tooltip>
          <el-tooltip content="编辑源码" placement="top">
            <button class="note-icon-btn" @click="startEdit"><el-icon><EditPen /></el-icon></button>
          </el-tooltip>
          <el-tooltip content="自适应" placement="top">
            <button class="note-icon-btn" @click="fitToScreen"><el-icon><Aim /></el-icon></button>
          </el-tooltip>
          <el-tooltip content="放大" placement="top">
            <button class="note-icon-btn" @click="zoomBy(1.2)"><el-icon><ZoomIn /></el-icon></button>
          </el-tooltip>
          <el-tooltip content="缩小" placement="top">
            <button class="note-icon-btn" @click="zoomBy(1 / 1.2)"><el-icon><ZoomOut /></el-icon></button>
          </el-tooltip>
          <el-tooltip :content="fullscreen ? '退出全屏' : '全屏'" placement="top">
            <button class="note-icon-btn" :class="fullscreen && 'bg-note-green text-white'" @click="toggleFullscreen">
              <el-icon><FullScreen /></el-icon>
            </button>
          </el-tooltip>
        </template>
      </div>
    </div>

    <!-- 编辑态: 源码编辑 -->
    <div v-if="editing" class="bg-[#10241a]">
      <textarea
        v-model="editCode"
        class="w-full min-h-[280px] max-h-[500px] p-3 border-none outline-none resize-y box-border font-mono text-[13px] leading-[1.6] text-[#dcebe0] bg-transparent"
        spellcheck="false"
        placeholder="请输入 mermaid 源码"
      />
    </div>

    <!-- 查看态: 画布(锁定=滚轮交给页面滚动; 解锁后滚轮缩放 + 拖拽平移) -->
    <div
      v-else
      ref="wrapperRef"
      class="relative p-4 overflow-hidden min-h-[420px] max-h-[70vh] select-none"
      :class="[
        dragging ? 'cursor-grabbing' : locked ? 'cursor-default' : 'cursor-grab',
        fullscreen ? 'flex-1 max-h-none' : '',
      ]"
      @wheel="onWheel"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
    >
      <div ref="containerRef" class="mm-canvas absolute top-0 left-0 min-h-20 will-change-transform" :style="transformStyle" />
    </div>

    <!-- 渲染错误提示 -->
    <div v-if="renderError && !editing" class="px-3 py-2 text-xs text-[#c0453e] bg-[#fbf6f4]">
      图表格式错误: {{ renderError }}
    </div>

    <!-- 离屏渲染容器: mermaid 临时 DOM 仅挂在此, 移出屏幕不影响页面 -->
    <div ref="offscreenRef" class="absolute -left-[9999px] -top-[9999px] w-[1200px] h-[800px] overflow-hidden pointer-events-none" aria-hidden="true" />
  </div>
</template>

<style scoped>
/* 流式生成中指示: 苔绿小胶囊脉动圆点(伪元素, UnoCSS 无法表达) */
.mm-live::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  animation: mm-pulse 1s ease-in-out infinite;
}

@keyframes mm-pulse {
  50% { opacity: 0.3; }
}

/* 增强字体与形状渲染质量 */
.mm-canvas :deep(svg) {
  display: block;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: optimizeLegibility;
  shape-rendering: geometricPrecision;
}
</style>
