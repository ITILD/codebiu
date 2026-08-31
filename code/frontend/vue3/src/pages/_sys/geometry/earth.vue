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
      </el-radio-group>

      <!-- 绘制操作按钮(仅绘制线/面时显示) -->
      <template v-if="drawMode === 'linestring' || drawMode === 'polygon'">
        <el-button
          type="primary" :disabled="draftPoints.length < (drawMode === 'polygon' ? 3 : 2)"
          @click="handleFinishDraft"
        >
          完成绘制
        </el-button>
        <el-button @click="handleCancelDraft">取消</el-button>
        <el-tag type="warning" effect="plain">
          已选 {{ draftPoints.length }} 点(单击加点, 双击结束)
        </el-tag>
      </template>
    </div>

    <!-- 主区域: 地球 + 右侧要素面板 -->
    <div flex flex-col lg:flex-row gap-4>
      <!-- 地球画布 -->
      <div
        flex-1 min-w-0 rounded-lg overflow-hidden relative
        class="h-[55vh] lg:h-[70vh]"
        bg-note-card border border-note shadow-note
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
            </template>
          </el-table-column>
          <el-table-column label="顶点" width="60" align="center">
            <template #default="{ row }">
              {{ vertexCount(row) }}
            </template>
          </el-table-column>
          <el-table-column label="更新时间" width="100" show-overflow-tooltip>
            <template #default="{ row }">
              {{ formatTime(row.updated_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" align="center">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="handleFocus(row)">定位</el-button>
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
    <el-dialog v-model="saveDialogVisible" title="保存要素" width="90%" class="max-w-[420px]">
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
      </el-form>
      <template #footer>
        <el-button @click="saveDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSave">保存到数据库</el-button>
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
import { Pointer, Location, Share, Grid } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import {
  createGeoFeature,
  deleteGeoFeature,
  listAllGeoFeatures,
  listGeoFeatures,
  updateGeoFeature,
} from '@/api/geometry/feature'
import TableSearchBar, { type SearchField } from '@/components/app/sys/TableSearchBar.vue'
import {
  featureTypeOptions,
  featureTypeTagType,
  type GeoFeature,
  type GeoJSONGeometry,
  type LngLat,
} from '@/types/geometry'
import type { PaginationParams, PaginationResponse } from '@/types/common'
import { EarthScene, type DrawMode, type DrawEvent } from './EarthScene'

// ################ 地球场景 ################
let earthScene: EarthScene | undefined
/** 当前绘制模式 */
const drawMode = ref<DrawMode>('none')
/** 绘制中已收集的点(用于完成按钮禁用判断) */
const draftPoints = ref<LngLat[]>([])

/** 各模式操作提示 */
const drawTips = computed(() => {
  switch (drawMode.value) {
    case 'point': return '点击地球表面放置标记点'
    case 'linestring': return '依次点击添加顶点, 双击或点"完成绘制"结束'
    case 'polygon': return '依次点击添加顶点, 双击或点"完成绘制"闭合'
    default: return ''
  }
})

/** 初始化场景与全量渲染 */
const initScene = () => {
  earthScene = new EarthScene('earthDom')
  earthScene.observeResize('earthCanvasP')
}

/** 设置绘制模式(切换时重置预览) */
const handleModeChange = (mode: string | number | boolean | undefined) => {
  draftPoints.value = []
  earthScene?.setDrawMode(mode as DrawMode, handleDrawEvent)
}

/** 绘制事件回调(点=单击完成, 线/面=双击或按钮完成) */
const handleDrawEvent = (e: DrawEvent) => {
  draftPoints.value = e.points
  if (e.finished) {
    pendingType.value = e.mode
    pendingCoords.value = e.points
    saveForm.value.name = defaultName(e.mode)
    saveDialogVisible.value = true
  }
}

/** 默认要素名 */
const defaultName = (mode: DrawMode) => {
  const now = new Date()
  const time = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
  const label = mode === 'point' ? '标记点' : mode === 'linestring' ? '路线' : '区域'
  return `${label}-${time}`
}

/** 完成绘制(按钮触发) */
const handleFinishDraft = () => earthScene?.finishDraft()

/** 取消绘制(保留浏览模式) */
const handleCancelDraft = () => {
  draftPoints.value = []
  earthScene?.clearDraft()
}

// ################ 保存对话框 ################
const saveDialogVisible = ref(false)
const saveFormRef = ref<FormInstance>()
const saveForm = ref({ name: '' })
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
    await createGeoFeature({ name: saveForm.value.name, geometry })
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

/** 经纬度点列转 GeoJSON 几何体 */
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
  await refreshAll()
})

onBeforeUnmount(() => {
  earthScene?.dispose()
  earthScene = undefined
})
</script>
