<template>
  <!-- 可拖动悬浮工具: 全屏 / 截图 / 隐藏(隐藏后可在 设置-外观 中重新开启)
       主题取值全部走 --note-* 变量, 明暗自动适配; 位置吸附左右边并持久化 -->
  <div
    v-if="!sysStore.floatToolsHidden"
    ref="rootRef"
    class="float-tools-root fixed z-50"
    :style="{ left: `${pos.x}px`, top: `${pos.y}px` }"
  >
    <!-- 展开菜单: 根据悬浮球位置向视口内侧弹出(上/下 + 左/右对齐) -->
    <Transition name="ft-pop">
      <div
        v-if="expanded"
        class="absolute flex flex-col gap-1.5 p-1"
        :class="menuAbove ? 'bottom-full' : 'top-full'"
        :style="menuStyle"
      >
        <button class="ft-pill" type="button" @click="toggleFullscreen">
          <i-ep-close v-if="isFullscreen" class="text-sm" />
          <i-ep-full-screen v-else class="text-sm" />
          {{ isFullscreen ? '退出全屏' : '全屏' }}
        </button>
        <button class="ft-pill" type="button" :disabled="shooting" @click="takeScreenshot">
          <i-ep-camera class="text-sm" />
          {{ shooting ? '截图中…' : '截图' }}
        </button>
        <button class="ft-pill" type="button" @click="hideTools">
          <i-ep-hide class="text-sm" />
          隐藏
        </button>
      </div>
    </Transition>

    <!-- 悬浮球: 拖动换位, 点击展开/收起 -->
    <button
      class="ft-knob"
      :class="{ 'is-dragging': dragging, 'is-open': expanded }"
      type="button"
      title="悬浮工具(拖动换位)"
      @pointerdown="onDown"
      @pointermove="onMove"
      @pointerup="onUp"
      @pointercancel="onUp"
    >
      <!-- 折纸和平鸽(左朝向): 三档苔绿折面拼接, 全走 --note-* 变量明暗自适应
           绘制顺序=纸的叠压关系: 尾羽在下层, 身体压住尾根, 翅膀/头颈在最上层 -->
      <svg class="ft-bird" viewBox="0 0 32 32" aria-hidden="true">
        <!-- 尾羽: 下层, 从身后向右下探出 -->
        <polygon points="24 14 28 27 14 20" fill="var(--note-accent)" />
        <polygon points="23 12 31 16 22 20" fill="var(--note-border-green)" />
        <!-- 躯干: 上折面(浅) + 下折面(中), 菱形折纸身体 -->
        <polygon points="8 12 23 9 27 15" fill="var(--note-border-green)" />
        <polygon points="8 12 27 15 13 21" fill="var(--note-green)" />
        <!-- 抬起的翅膀 -->
        <polygon points="13 2 23 9 11 13" fill="var(--note-green)" />
        <!-- 头颈 + 喙: 左朝向 -->
        <polygon points="8 7 13 11 8 12" fill="var(--note-green)" />
        <polygon points="2 9 8 7 8 12" fill="var(--note-accent)" />
        <!-- 眼: 纸色镂空 -->
        <circle cx="10" cy="9.2" r="0.9" fill="var(--note-paper)" />
      </svg>
    </button>
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'
import { SysSettingStore } from '@/common/stores/sys'

const sysStore = SysSettingStore()

// 悬浮球尺寸与贴边留白(px)
const KNOB = 46
const EDGE = 10
// 拖动判定阈值(位移超过该值视为拖拽, 否则视为点击)
const DRAG_THRESHOLD = 6

const rootRef = ref<HTMLElement | null>(null)
const expanded = ref(false)
const dragging = ref(false)
const shooting = ref(false)
const isFullscreen = ref(Boolean(document.fullscreenElement))

/////////////////////////////////////////////////////////位置持久化/////////////////////////////////////////////////////////
const clampPos = (p: { x: number; y: number }) => ({
  x: Math.min(Math.max(p.x, EDGE), window.innerWidth - KNOB - EDGE),
  y: Math.min(Math.max(p.y, EDGE), window.innerHeight - KNOB - EDGE)
})

const loadPos = () => {
  try {
    const saved = localStorage.getItem('sys-float-tools-pos')
    if (saved) return clampPos(JSON.parse(saved))
  } catch { /* 忽略损坏的存档, 回落默认位置 */ }
  // 默认: 右侧偏下(避开吸顶导航)
  return clampPos({ x: window.innerWidth - KNOB - EDGE, y: window.innerHeight * 0.72 })
}

const pos = ref(loadPos())
const savePos = () => localStorage.setItem('sys-float-tools-pos', JSON.stringify(pos.value))

// 菜单弹出方向: 悬浮球在视口下半部时向上弹, 右半部时右对齐
const menuAbove = computed(() => pos.value.y + KNOB / 2 > window.innerHeight / 2)
const menuStyle = computed(() => ({
  left: pos.value.x + KNOB / 2 <= window.innerWidth / 2 ? '0' : 'auto',
  right: pos.value.x + KNOB / 2 > window.innerWidth / 2 ? '0' : 'auto',
  marginBottom: menuAbove.value ? '8px' : undefined,
  marginTop: menuAbove.value ? undefined : '8px',
  transformOrigin: menuAbove.value ? 'bottom right' : 'top right'
}))

/////////////////////////////////////////////////////////拖拽(指针事件统一鼠标/触摸)/////////////////////////////////////////////////////////
const dragStart = { px: 0, py: 0, x: 0, y: 0, moved: false }

const onDown = (e: PointerEvent) => {
  if (e.pointerType === 'mouse' && e.button !== 0) return
  e.preventDefault()
  ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
  dragStart.px = e.clientX
  dragStart.py = e.clientY
  dragStart.x = pos.value.x
  dragStart.y = pos.value.y
  dragStart.moved = false
}

const onMove = (e: PointerEvent) => {
  if (!e.buttons && e.pointerType === 'mouse') return
  const dx = e.clientX - dragStart.px
  const dy = e.clientY - dragStart.py
  if (!dragStart.moved && Math.hypot(dx, dy) < DRAG_THRESHOLD) return
  dragStart.moved = true
  dragging.value = true
  pos.value = clampPos({ x: dragStart.x + dx, y: dragStart.y + dy })
}

const onUp = () => {
  if (dragStart.moved) {
    // 松手吸附到最近的左右边
    pos.value.x = pos.value.x + KNOB / 2 <= window.innerWidth / 2 ? EDGE : window.innerWidth - KNOB - EDGE
    savePos()
  } else {
    expanded.value = !expanded.value
  }
  dragging.value = false
}

/////////////////////////////////////////////////////////全局监听/////////////////////////////////////////////////////////
// 点击悬浮球以外区域时收起菜单
const onDocDown = (e: PointerEvent) => {
  if (expanded.value && rootRef.value && !rootRef.value.contains(e.target as Node)) expanded.value = false
}
// 视口变化时把悬浮球夹回可视范围
const onResize = () => { pos.value = clampPos(pos.value) }
// 同步全屏状态(用户用 Esc 退出时按钮文案要跟着变)
const onFsChange = () => { isFullscreen.value = Boolean(document.fullscreenElement) }

onMounted(() => {
  document.addEventListener('pointerdown', onDocDown, true)
  document.addEventListener('fullscreenchange', onFsChange)
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocDown, true)
  document.removeEventListener('fullscreenchange', onFsChange)
  window.removeEventListener('resize', onResize)
})

/////////////////////////////////////////////////////////功能动作/////////////////////////////////////////////////////////
const toggleFullscreen = async () => {
  expanded.value = false
  try {
    if (document.fullscreenElement) await document.exitFullscreen()
    else await document.documentElement.requestFullscreen()
  } catch {
    ElMessage.warning('当前环境不允许全屏')
  }
}

// 整页截图: html2canvas 动态引入(不占首包), 悬浮工具自身不参与截图
const takeScreenshot = async () => {
  expanded.value = false
  if (shooting.value) return
  shooting.value = true
  try {
    const { default: html2canvas } = await import('html2canvas')
    const canvas = await html2canvas(document.body, {
      useCORS: true,
      backgroundColor: null,
      ignoreElements: (el) => el.classList?.contains('float-tools-root')
    })
    const a = document.createElement('a')
    a.download = `screenshot_${dayjs().format('YYYYMMDD-HHmmss')}.png`
    a.href = canvas.toDataURL('image/png')
    a.click()
    ElMessage.success('截图已保存')
  } catch {
    ElMessage.error('截图失败')
  } finally {
    shooting.value = false
  }
}

const hideTools = () => {
  expanded.value = false
  sysStore.floatToolsHidden = true
  ElMessage.info('悬浮工具已隐藏, 可在 设置-外观 中重新开启')
}
</script>

<style scoped>
/* 悬浮球: 毛玻璃纸底 + 光晕环纸影(与吸顶导航同配方), 拖动时抬升 */
.ft-knob {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 46px;
  height: 46px;
  border: none;
  border-radius: 9999px;
  background: var(--note-glass);
  color: var(--note-accent);
  box-shadow: var(--note-shadow);
  cursor: pointer;
  user-select: none;
  touch-action: none;
  transition: box-shadow 0.2s ease-out, transform 0.2s ease-out;
}

.ft-knob:hover {
  box-shadow: var(--note-shadow-hover);
}

.ft-knob:active {
  transform: scale(0.94);
}

.ft-knob.is-dragging {
  box-shadow: var(--note-shadow-hover);
  transition: none;
}

/* 剪纸小鸟: 展开菜单时轻轻抬头 */
.ft-bird {
  width: 24px;
  height: 24px;
  transition: transform 0.2s ease-out;
}

.ft-knob.is-open .ft-bird {
  transform: rotate(-14deg);
}

/* 菜单项: 无边线药丸, 底色差 + 纸影定义形状 */
.ft-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 36px;
  padding: 0 14px;
  border: none;
  border-radius: 9999px;
  background: var(--note-card);
  color: var(--note-sub);
  font-size: 12px;
  white-space: nowrap;
  box-shadow: var(--note-shadow);
  cursor: pointer;
  transition: all 0.2s ease-out;
}

.ft-pill:hover {
  background: var(--note-tint);
  color: var(--note-accent);
}

.ft-pill:disabled {
  opacity: 0.6;
  cursor: default;
}

/* 菜单弹出/收起: 缩放 + 淡入淡出, 原点朝向悬浮球 */
.ft-pop-enter-active,
.ft-pop-leave-active {
  transition: opacity 0.18s ease-out, transform 0.18s ease-out;
}

.ft-pop-enter-from,
.ft-pop-leave-to {
  opacity: 0;
  transform: scale(0.88);
}
</style>
