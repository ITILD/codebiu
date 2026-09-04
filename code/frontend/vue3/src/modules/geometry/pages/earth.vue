<template>
  <div p-4 md:p-6 w-full flex flex-col gap-4>
    <!-- 绘制工具栏 -->
    <div flex flex-wrap items-center gap-3>
      <el-radio-group v-model="drawMode" @change="handleModeChange">
        <el-radio-button value="none">
          <el-icon mr-1><Pointer /></el-icon>浏览
        </el-radio-button>
        <el-radio-button value="point">
          <el-icon mr-1><Location /></el-icon>画点
        </el-radio-button>
        <el-radio-button value="linestring">
          <el-icon mr-1><Share /></el-icon>画线
        </el-radio-button>
        <el-radio-button value="polygon">
          <el-icon mr-1><Grid /></el-icon>画面
        </el-radio-button>
        <el-radio-button value="extrude">
          <el-icon mr-1><Box /></el-icon>立体
        </el-radio-button>
      </el-radio-group>

      <!-- 绘制操作按钮(仅绘制线/面/立体时显示) -->
      <template v-if="drawMode === 'linestring' || drawMode === 'polygon' || drawMode === 'extrude'">
        <el-button
          type="primary" :disabled="draftPoints.length < (drawMode === 'linestring' ? 2 : 3)"
          @click="handleFinishDraft"
        >
          完成绘制
        </el-button>
        <el-button :disabled="!draftPoints.length" @click="handleUndoDraft">撤销</el-button>
        <el-button @click="handleCancelDraft">取消</el-button>
        <el-tag type="warning" effect="plain">
          已选 {{ draftPoints.length }} 点(单击加点, 双击结束, Ctrl+Z 撤销)
        </el-tag>
      </template>
    </div>

    <!-- 主区域: 地球 + 右侧要素面板 -->
    <div flex flex-col lg:flex-row gap-4>
      <!-- 地球画布(绘制模式下指针变十字, 浏览时抓手) -->
      <div
        flex-1 min-w-0 rounded-lg overflow-hidden relative
        class="h-[55vh] lg:h-[70vh]"
        bg-note-card border border-note shadow-note
        :style="{ cursor: drawMode === 'none' ? 'grab' : 'crosshair' }"
      >
        <div id="earthCanvasP" w-full h-full absolute>
          <canvas id="earthDom" w-full h-full></canvas>
        </div>
        <!-- 绘制模式提示角标 -->
        <div
          v-if="drawMode !== 'none'"
          absolute top-3 left-3 z-10 px-3 py-1.5 rounded-full
          bg-note-card border border-note text-sm text-note
        >
          {{ drawTips }}
        </div>
        <!-- 指针所指地表坐标(绘制模式下实时显示) -->
        <div
          v-if="hoverLngLat"
          absolute bottom-3 left-3 z-10 px-3 py-1.5 rounded-full
          bg-note-card border border-note text-xs text-note-sub
        >
          经度 {{ hoverLngLat.lon.toFixed(2) }}° · 纬度 {{ hoverLngLat.lat.toFixed(2) }}°
        </div>
      </div>

      <!-- 右侧: 要素列表 -->
      <div w-full lg:w-96 shrink-0 flex flex-col gap-3>
        <!-- 搜索栏 -->
        <TableSearchBar
          v-model="queryParams"
          :fields="searchFields"
          :collapse-count="2"
          @search="handleSearch"
          @reset="handleSearch"
        />

        <!-- 表格 -->
        <el-table :data="tableData" v-loading="loading" stripe w-full>
          <el-table-column prop="name" label="名称" min-width="110" show-overflow-tooltip />
          <el-table-column label="类型" width="70" align="center">
            <template #default="{ row }">
              <el-tag :type="tagType(row.feature_type)" size="small">
                {{ featureTypeLabel(row.feature_type) }}
              </el-tag>
              <!-- 立体物标记(面要素拉伸后 feature_type 仍为 polygon, 以 style.height 区分) -->
              <el-tag v-if="(row.style?.height ?? 0) > 0" size="small" type="warning" effect="plain" class="ml-1">
                3D
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="顶点" width="60" align="center">
            <template #default="{ row }">
              {{ vertexCount(row) }}
            </template>
          </el-table-column>
          <el-table-column label="样式" width="64" align="center">
            <template #default="{ row }">
              <span
                inline-block w-3.5 h-3.5 rounded-full border border-note align-middle
                :style="{ backgroundColor: resolveStyle(row.feature_type, row.style).color }"
              />
            </template>
          </el-table-column>
          <el-table-column label="更新时间" width="100" show-overflow-tooltip>
            <template #default="{ row }">
              {{ formatTime(row.updated_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="186" align="center">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="handleFocus(row)">定位</el-button>
              <el-button link type="primary" size="small" @click="handleStyle(row)">样式</el-button>
              <el-button link type="primary" size="small" @click="handleRename(row)">重命名</el-button>
              <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 分页 -->
        <div flex justify-end>
          <el-pagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.size"
            :total="total"
            layout="total, prev, pager, next"
            @size-change="fetchData"
            @current-change="fetchData"
          />
        </div>
      </div>
    </div>

    <!-- 保存要素命名对话框 -->
    <el-dialog v-model="saveDialogVisible" title="保存要素" width="90%" class="max-w-[480px]">
      <el-form :model="saveForm" ref="saveFormRef" :rules="saveRules" label-width="80px">
        <el-form-item label="类型">
          <el-tag :type="tagType(pendingType)">
            {{ featureTypeLabel(pendingType) }}
          </el-tag>
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="saveForm.name" placeholder="请输入要素名称" maxlength="100" />
        </el-form-item>
        <el-form-item label="坐标">
          <div text-xs text-note-sub break-all leading-5>
            {{ previewCoords }}
          </div>
        </el-form-item>
        <!-- 渲染样式(以 JSON 存入数据库 style 字段) -->
        <el-form-item label="样式">
          <div w-full flex flex-col gap-2>
            <div flex items-center gap-2>
              <span text-xs text-note-sub w-10>颜色</span>
              <el-color-picker v-model="saveForm.style.color" />
              <span text-xs text-note-sub>{{ saveForm.style.color }}</span>
            </div>
            <div flex items-center gap-2>
              <span text-xs text-note-sub w-10>透明度</span>
              <el-slider
                v-model="saveForm.style.opacity" :min="0.1" :max="1" :step="0.05"
                w-40 show-input :show-input-controls="false" input-size="small"
              />
            </div>
            <div flex items-center gap-2>
              <span text-xs text-note-sub w-10>粗细</span>
              <el-slider
                v-model="saveForm.style.width" :min="0.5" :max="3" :step="0.5"
                w-40 show-input :show-input-controls="false" input-size="small"
              />
            </div>
            <!-- 立体物拉伸高度(存于 style.height, 预览实时更新) -->
            <div v-if="pendingType === 'extrude'" flex items-center gap-2>
              <span text-xs text-note-sub w-10>高度</span>
              <el-slider
                v-model="saveForm.style.height" :min="0.01" :max="0.4" :step="0.01"
                w-40 show-input :show-input-controls="false" input-size="small"
              />
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="saveDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSave">保存到数据库</el-button>
      </template>
    </el-dialog>

    <!-- 样式编辑对话框 -->
    <el-dialog v-model="styleDialogVisible" title="编辑样式" width="90%" class="max-w-[480px]">
      <div flex flex-col gap-4 py-2>
        <div flex items-center gap-3>
          <span text-sm text-note w-12>颜色</span>
          <el-color-picker v-model="styleForm.color" />
          <span text-xs text-note-sub>{{ styleForm.color }}</span>
        </div>
        <div flex items-center gap-3>
          <span text-sm text-note w-12>透明度</span>
          <el-slider
            v-model="styleForm.opacity" :min="0.1" :max="1" :step="0.05"
            flex-1 show-input :show-input-controls="false" input-size="small"
          />
        </div>
        <div flex items-center gap-3>
          <span text-sm text-note w-12>粗细</span>
          <el-slider
            v-model="styleForm.width" :min="0.5" :max="3" :step="0.5"
            flex-1 show-input :show-input-controls="false" input-size="small"
          />
        </div>
        <!-- 拉伸高度(仅面要素, >0 渲染为立体棱柱) -->
        <div v-if="styleTarget?.feature_type === 'polygon'" flex items-center gap-3>
          <span text-sm text-note w-12>高度</span>
          <el-slider
            v-model="styleForm.height" :min="0" :max="0.4" :step="0.01"
            flex-1 show-input :show-input-controls="false" input-size="small"
          />
        </div>
        <el-alert type="info" :closable="false" show-icon>
          <template #title>
            样式以 JSON 存储于要素的 style 字段, 保存后立即在地球上生效
          </template>
        </el-alert>
      </div>
      <template #footer>
        <el-button @click="styleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleStyleSubmit">保存样式</el-button>
      </template>
    </el-dialog>

    <!-- 重命名对话框 -->
    <el-dialog v-model="renameDialogVisible" title="重命名要素" width="90%" class="max-w-[420px]">
      <el-input v-model="renameName" placeholder="请输入新名称" maxlength="100" />
      <template #footer>
        <el-button @click="renameDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleRenameSubmit">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Pointer, Location, Share, Grid, Box } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import {
  createGeoFeature,
  deleteGeoFeature,
  getGeoFeature,
  listAllGeoFeatures,
  listGeoFeatures,
  updateGeoFeature,
} from '../api/feature'
import TableSearchBar, { type SearchField } from '@/common/components/TableSearchBar.vue'
import {
  defaultExtrudeStyle,
  defaultFeatureStyles,
  FeatureType,
  featureTypeOptions,
  featureTypeTagType,
  resolveStyle,
  type GeoFeature,
  type GeoFeatureStyle,
  type GeoJSONGeometry,
  type LngLat,
} from '../types'
import type { PaginationParams, PaginationResponse } from '@/common/types/common'
import { EarthScene, type DrawMode, type DrawEvent } from '../utils/EarthScene'

// ################ 地球场景 ################
let earthScene: EarthScene | undefined
/** 当前绘制模式 */
const drawMode = ref<DrawMode>('none')
/** 绘制中已收集的点(用于完成按钮禁用判断) */
const draftPoints = ref<LngLat[]>([])
/** 绘制模式下指针所指地表坐标(实时显示) */
const hoverLngLat = ref<LngLat | null>(null)

/** 各模式操作提示 */
const drawTips = computed(() => {
  switch (drawMode.value) {
    case 'point': return '点击地球表面放置标记点'
    case 'linestring': return '依次点击添加顶点, 双击或点"完成绘制"结束'
    case 'polygon': return '依次点击添加顶点, 双击或点"完成绘制"闭合'
    case 'extrude': return '点击绘制底面轮廓, 双击结束, 保存时可调整高度'
    default: return ''
  }
})

/** 初始化场景与全量渲染 */
const initScene = () => {
  earthScene = new EarthScene('earthDom')
  earthScene.observeResize('earthCanvasP')
  // 绘制模式下指针悬停实时回显地表坐标
  earthScene.setHoverCallback((p) => {
    hoverLngLat.value = p
  })
}

/** 设置绘制模式(切换时重置预览) */
const handleModeChange = (mode: string | number | boolean | undefined) => {
  draftPoints.value = []
  earthScene?.setDrawMode(mode as DrawMode, handleDrawEvent)
}

/** 绘制事件回调(点=单击完成, 线/面/立体=双击或按钮完成) */
const handleDrawEvent = (e: DrawEvent) => {
  draftPoints.value = e.points
  if (e.finished) {
    pendingType.value = e.mode
    pendingCoords.value = e.points
    // 按类型初始化默认样式(立体物使用拉伸默认样式, 预览实时同步)
    saveForm.value.style = e.mode === 'extrude'
      ? { ...defaultExtrudeStyle }
      : { ...defaultFeatureStyles[e.mode as FeatureType] }
    saveForm.value.name = defaultName(e.mode)
    saveDialogVisible.value = true
  }
}

/** 默认要素名 */
const defaultName = (mode: DrawMode) => {
  const now = new Date()
  const time = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
  const label = mode === 'point'
    ? '标记点'
    : mode === 'linestring'
      ? '路线'
      : mode === 'extrude'
        ? '立体物'
        : '区域'
  return `${label}-${time}`
}

/** 完成绘制(按钮触发) */
const handleFinishDraft = () => earthScene?.finishDraft()

/** 撤销上一个顶点 */
const handleUndoDraft = () => earthScene?.undoDraftPoint()

/** 取消绘制(保留浏览模式) */
const handleCancelDraft = () => {
  draftPoints.value = []
  earthScene?.clearDraft()
}

/** 键盘快捷键: Esc 取消绘制, Ctrl/Cmd+Z 撤销顶点 */
const handleKeydown = (e: KeyboardEvent) => {
  if (drawMode.value === 'none') return
  if (e.key === 'Escape') {
    handleCancelDraft()
  }
  else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
    e.preventDefault()
    handleUndoDraft()
  }
}

// ################ 保存对话框 ################
const saveDialogVisible = ref(false)
const saveFormRef = ref<FormInstance>()
const saveForm = ref<{ name: string, style: Required<GeoFeatureStyle> }>({
  name: '',
  style: { ...defaultFeatureStyles[FeatureType.POINT] },
})
const saveRules = {
  name: [
    { required: true, message: '请输入要素名称', trigger: 'blur' },
    { min: 1, max: 100, message: '长度在 1 到 100 个字符', trigger: 'blur' },
  ],
}
/** 待保存的类型与坐标 */
const pendingType = ref<DrawMode>('point')
const pendingCoords = ref<LngLat[]>([])
const submitting = ref(false)

// 保存对话框关闭(取消/保存)时清理地球上的预览
watch(saveDialogVisible, (visible) => {
  if (!visible) {
    draftPoints.value = []
    earthScene?.clearDraft()
  }
})

// 样式调整实时同步到地球上的成品预览(所见即所得)
watch(
  () => saveForm.value.style,
  (style) => earthScene?.updateDraftPreview({ ...style }),
  { deep: true },
)

/** 坐标预览文本 */
const previewCoords = computed(() => {
  const pts = pendingCoords.value
  if (!pts.length) return ''
  const head = pts
    .slice(0, 4)
    .map(p => `(${p.lon.toFixed(3)}, ${p.lat.toFixed(3)})`)
    .join(' ')
  return pts.length > 4 ? `${head} ... 共 ${pts.length} 点` : head
})

/** 保存要素到 PostGIS */
const handleSave = async () => {
  const valid = await saveFormRef.value?.validate().catch(() => false)
  if (!valid) return

  const geometry = buildGeometry(pendingType.value, pendingCoords.value)
  if (!geometry) return

  try {
    submitting.value = true
    await createGeoFeature({
      name: saveForm.value.name,
      geometry,
      style: { ...saveForm.value.style },
    })
    ElMessage.success('要素已保存')
    saveDialogVisible.value = false
    handleModeChange('none')
    drawMode.value = 'none'
    await refreshAll()
  }
  catch (error) {
    console.error('保存要素失败:', error)
    ElMessage.error('保存失败, 请重试')
  }
  finally {
    submitting.value = false
  }
}

/** 经纬度点列转 GeoJSON 几何体(立体物 extrude 以 Polygon 底面存储, 高度在 style.height) */
const buildGeometry = (mode: DrawMode, points: LngLat[]): GeoJSONGeometry | null => {
  if (mode === 'point') {
    const p = points[0]
    if (!p) return null
    return { type: 'Point', coordinates: [p.lon, p.lat] }
  }
  const coords = points.map(p => [p.lon, p.lat])
  if (mode === 'linestring') {
    if (coords.length < 2) {
      ElMessage.warning('线要素至少需要 2 个顶点')
      return null
    }
    return { type: 'LineString', coordinates: coords }
  }
  if (coords.length < 3) {
    ElMessage.warning('面要素至少需要 3 个顶点')
    return null
  }
  // 首尾闭合
  const ring = [...coords, coords[0]]
  return { type: 'Polygon', coordinates: [ring] }
}

// ################ 列表与搜索 ################
const loading = ref(false)
const tableData = ref<GeoFeature[]>([])
const total = ref(0)
const pagination = ref<PaginationParams>({ page: 1, size: 10 })

// 搜索字段配置(名称/类型多字段筛选)
const searchFields: SearchField[] = [
  { prop: 'keyword', label: '名称' },
  {
    prop: 'feature_type', label: '类型', type: 'select',
    options: featureTypeOptions.map(o => ({ label: o.label, value: o.value as string })),
  },
]
// 查询参数(与后端列表接口过滤参数对齐)
const queryParams = ref<Record<string, unknown>>({
  keyword: '',
  feature_type: undefined,
})

/** 获取列表(携带多字段过滤参数) */
const fetchData = async () => {
  try {
    loading.value = true
    const { keyword, feature_type } = queryParams.value
    const res: PaginationResponse<GeoFeature> = await listGeoFeatures({
      ...pagination.value,
      keyword: (keyword as string) || undefined,
      feature_type: (feature_type as string) || undefined,
    })
    tableData.value = res.items
    total.value = res.total
  }
  catch (error) {
    console.error('获取要素列表失败:', error)
    ElMessage.error('获取要素列表失败')
  }
  finally {
    loading.value = false
  }
}

/** 搜索/重置: 回到第一页后重新查询 */
const handleSearch = () => {
  pagination.value.page = 1
  fetchData()
}

/** 刷新球渲染 + 列表 */
const refreshAll = async () => {
  try {
    const all = await listAllGeoFeatures()
    earthScene?.renderFeatures(all)
  }
  catch (error) {
    console.error('刷新地球渲染失败:', error)
  }
  await fetchData()
}

// ################ 行操作 ################
/** 类型中文标签 */
const featureTypeLabel = (type: string) =>
  featureTypeOptions.find(o => o.value === type)?.label ?? type

/** 类型标签样式(容错返回 info) */
type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'
const tagType = (type: string): TagType =>
  (featureTypeTagType as Record<string, TagType>)[type] ?? 'info'

/** 顶点数量 */
const vertexCount = (row: GeoFeature) => {
  if (row.geometry.type === 'Point') return 1
  if (row.geometry.type === 'LineString') return (row.geometry.coordinates as number[][]).length
  const ring = (row.geometry.coordinates as number[][][])[0] ?? []
  return Math.max(0, ring.length - 1)
}

/** 时间格式化 */
const formatTime = (value: string) =>
  new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })

/** 定位要素 */
const handleFocus = (row: GeoFeature) => earthScene?.focusFeature(row)

/** 重命名 */
const renameDialogVisible = ref(false)
const renameName = ref('')
const renameTarget = ref<GeoFeature | null>(null)

const handleRename = (row: GeoFeature) => {
  renameTarget.value = row
  renameName.value = row.name
  renameDialogVisible.value = true
}

const handleRenameSubmit = async () => {
  if (!renameTarget.value || !renameName.value.trim()) {
    ElMessage.warning('名称不能为空')
    return
  }
  try {
    submitting.value = true
    await updateGeoFeature(renameTarget.value.id, { name: renameName.value.trim() })
    ElMessage.success('重命名成功')
    renameDialogVisible.value = false
    await fetchData()
  }
  catch (error) {
    console.error('重命名失败:', error)
    ElMessage.error('重命名失败')
  }
  finally {
    submitting.value = false
  }
}

/** 样式编辑(保存后单要素重渲染) */
const styleDialogVisible = ref(false)
const styleTarget = ref<GeoFeature | null>(null)
const styleForm = ref<Required<GeoFeatureStyle>>({ ...defaultFeatureStyles[FeatureType.POINT] })

const handleStyle = (row: GeoFeature) => {
  styleTarget.value = row
  styleForm.value = resolveStyle(row.feature_type, row.style)
  styleDialogVisible.value = true
}

const handleStyleSubmit = async () => {
  if (!styleTarget.value) return
  try {
    submitting.value = true
    const style: GeoFeatureStyle = { ...styleForm.value }
    await updateGeoFeature(styleTarget.value.id, { style })
    // 取最新数据后仅重渲染该要素
    const updated = await getGeoFeature(styleTarget.value.id)
    earthScene?.renderFeature(updated)
    ElMessage.success('样式已更新')
    styleDialogVisible.value = false
    await fetchData()
  }
  catch (error) {
    console.error('样式更新失败:', error)
    ElMessage.error('样式更新失败')
  }
  finally {
    submitting.value = false
  }
}

/** 删除要素 */
const handleDelete = (row: GeoFeature) => {
  ElMessageBox.confirm(
    `确定删除要素「${row.name}」吗? 将同时移除地球上的渲染。`,
    '删除确认',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  )
    .then(async () => {
      try {
        await deleteGeoFeature(row.id)
        earthScene?.removeFeature(row.id)
        ElMessage.success('删除成功')
        // 处理空页情况
        if (tableData.value.length === 1 && pagination.value.page > 1) {
          pagination.value.page -= 1
        }
        await fetchData()
      }
      catch (error) {
        console.error('删除要素失败:', error)
        ElMessage.error('删除失败')
      }
    })
    .catch(() => {})
}

// ################ 生命周期 ################
onMounted(async () => {
  initScene()
  window.addEventListener('keydown', handleKeydown)
  await refreshAll()
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeydown)
  earthScene?.dispose()
  earthScene = undefined
})
</script>
