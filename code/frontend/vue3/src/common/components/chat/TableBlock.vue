<script setup lang="ts">
// Markdown 表格区块: 工具栏支持导出 Excel / 复制 Markdown / 复制 TSV / 行内编辑
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import {
  Download, DocumentCopy, Grid, EditPen, Check, Close,
} from '@element-plus/icons-vue'
import {
  exportTableToExcel,
  tableToMarkdown,
  tableToTSV,
  copyToClipboard,
} from '@/common/utils/export'
import { renderMarkdownWithLatex } from '@/common/utils/latex'

interface Props {
  /** 表格 markdown 源码 */
  markdown: string
  /** 区块唯一ID(导出文件名) */
  blockId: string
}

const props = defineProps<Props>()

// 用户编辑后的覆盖值(未编辑时跟随 props)
const editedMd = ref<string | null>(null)
const editing = ref(false)
const editContent = ref('')
const tableWrapRef = ref<HTMLElement | null>(null)

const localMd = computed(() => editedMd.value ?? props.markdown)

// blockId 变化时清除本地编辑覆盖
watch(
  () => props.blockId,
  () => { editedMd.value = null },
)

/** 渲染表格 HTML(latex 保护, 仅取 <table> 部分) */
const tableHtml = computed(() => {
  const html = renderMarkdownWithLatex(
    (t) => marked.parse(t, { async: false }) as string,
    localMd.value,
  )
  return html.match(/<table[\s\S]*?<\/table>/)?.[0] ?? html
})

const getTableEl = () => tableWrapRef.value?.querySelector('table') ?? null

/** 校验是否为包含数据行的合法表格 markdown */
const isValidTableMd = (md: string) => {
  const [header, separator, firstRow] = md
    .trim()
    .split(/\r?\n/)
    .filter((line) => line.trim())
  if (!header || !separator || !firstRow) return false
  return (
    [header, separator, firstRow].every((line) => line.includes('|')) &&
    separator.includes('-') &&
    /^[|\s:-]+$/.test(separator)
  )
}

const startEdit = () => {
  editContent.value = localMd.value
  editing.value = true
}

const commitEdit = () => {
  if (!isValidTableMd(editContent.value)) {
    ElMessage.error('Markdown 解析失败，请检查表格格式')
    return
  }
  editedMd.value = editContent.value
  editing.value = false
  ElMessage.success('已更新表格')
}

const cancelEdit = () => { editing.value = false }

/** 导出 Excel */
const handleExportExcel = async () => {
  const table = getTableEl()
  if (!table) return
  try {
    await exportTableToExcel(table, `表格-${props.blockId}`)
    ElMessage.success('表格已导出')
  } catch (error) {
    ElMessage.error(`导出失败: ${error instanceof Error ? error.message : '未知错误'}`)
  }
}

/** 复制表格(Markdown 或 TSV 格式) */
const handleCopy = async (format: 'md' | 'excel') => {
  const table = getTableEl()
  if (!table) return
  const text = format === 'md' ? tableToMarkdown(table) : tableToTSV(table)
  if (!(await copyToClipboard(text))) {
    ElMessage.error('复制失败')
    return
  }
  ElMessage.success(format === 'md' ? '已复制 Markdown' : '已复制 Excel 格式')
}
</script>

<template>
  <div class="tb-block">
    <!-- 顶部: 标题 + 工具栏 -->
    <div class="tb-head">
      <span class="tb-title">表格</span>
      <div class="tb-tools">
        <template v-if="!editing">
          <el-tooltip content="导出 Excel" placement="top">
            <button class="tb-btn" @click="handleExportExcel"><el-icon><Download /></el-icon></button>
          </el-tooltip>
          <el-tooltip content="复制 Markdown" placement="top">
            <button class="tb-btn" @click="handleCopy('md')"><el-icon><DocumentCopy /></el-icon></button>
          </el-tooltip>
          <el-tooltip content="复制 Excel 格式" placement="top">
            <button class="tb-btn" @click="handleCopy('excel')"><el-icon><Grid /></el-icon></button>
          </el-tooltip>
          <el-tooltip content="编辑" placement="top">
            <button class="tb-btn primary" @click="startEdit"><el-icon><EditPen /></el-icon></button>
          </el-tooltip>
        </template>
        <template v-else>
          <el-tooltip content="确认" placement="top">
            <button class="tb-btn primary" @click="commitEdit"><el-icon><Check /></el-icon></button>
          </el-tooltip>
          <el-tooltip content="取消" placement="top">
            <button class="tb-btn" @click="cancelEdit"><el-icon><Close /></el-icon></button>
          </el-tooltip>
        </template>
      </div>
    </div>

    <!-- 查看态: 渲染表格 -->
    <div v-show="!editing" ref="tableWrapRef" class="tb-content" v-html="tableHtml" />

    <!-- 编辑态: textarea -->
    <textarea
      v-if="editing"
      v-model="editContent"
      class="tb-textarea"
      spellcheck="false"
    />
  </div>
</template>

<style scoped>
.tb-block {
  margin: 12px 0;
  border: 1px solid var(--note-border, #e2e8e3);
  border-radius: 12px;
  overflow: hidden;
  background: var(--note-card, #fdfefc);
}

.tb-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  background: var(--note-soft, #f2f7f0);
  border-bottom: 1px solid var(--note-border, #e2e8e3);
}

.tb-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--note-green-deep, #3f7a52);
}

.tb-tools {
  display: flex;
  align-items: center;
  gap: 2px;
}

.tb-btn {
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

.tb-btn:hover {
  background: var(--note-tint, #e7f3e9);
  color: var(--note-green, #6cbf8f);
}

.tb-btn.primary {
  background: var(--note-green, #6cbf8f);
  color: #fff;
}

.tb-content {
  overflow-x: auto;
  padding: 4px 0;
}

.tb-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 0;
  font-size: 13px;
}

.tb-content :deep(th),
.tb-content :deep(td) {
  border: 1px solid var(--note-border, #e2e8e3);
  padding: 6px 12px;
  text-align: left;
}

.tb-content :deep(th) {
  background: var(--note-soft, #f2f7f0);
  font-weight: 600;
}

.tb-content :deep(tr:nth-child(even)) {
  background: var(--note-card, #fbfdf9);
}

.tb-textarea {
  width: 100%;
  min-height: 160px;
  padding: 12px;
  border: none;
  outline: none;
  resize: vertical;
  font-family: ui-monospace, Consolas, monospace;
  font-size: 13px;
  line-height: 1.6;
  color: var(--el-text-color-primary, #2b3a30);
  background: var(--note-card, #fdfefc);
  box-sizing: border-box;
}
</style>
