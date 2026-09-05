<template>
  <!-- 全屏页(路由 meta.fullpage): 画布铺满除侧边栏外的整个子页面, 文档锁定滚动(滚轮留给场景缩放) -->
  <div relative w-full overflow-hidden class="h-[calc(100vh-3.5rem)] md:h-[calc(100vh-4rem)]">
    <!-- 三维画布(铺满底层; 绘制模式下指针变十字, 浏览时抓手) -->
    <div id="earthCanvasP" absolute inset-0 :style="{ cursor: drawMode === 'none' ? 'grab' : 'crosshair' }">
      <canvas id="earthDom" w-full h-full></canvas>
    </div>

    <!-- 顶部悬浮: 浏览/绘制工具栏 -->
    <div absolute top-3 left-3 right-3 z-20 flex justify-center pointer-events-none>
      <div
        pointer-events-auto
        class="flex flex-wrap items-center justify-center gap-2 rounded-lg border border-note bg-note-glass px-3 py-2 shadow-note backdrop-blur-md"
      >
        <el-radio-group v-model="drawMode" size="small" @change="handleModeChange">
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
            type="primary" size="small"
            :disabled="draftPoints.length < (drawMode === 'linestring' ? 2 : 3)"
            @click="handleFinishDraft"
          >
            完成绘制
          </el-button>
          <el-button size="small" :disabled="!draftPoints.length" @click="handleUndoDraft">撤销</el-button>
          <el-button size="small" @click="handleCancelDraft">取消</el-button>
        </template>
        <!-- 模式提示/进度角标 -->
        <el-tag v-if="drawMode !== 'none'" type="warning" effect="plain" size="small">
          {{ toolbarTips }}
        </el-tag>
      </div>
    </div>

    <!-- 左侧悬浮: 图层面板 + 各图层要素列表 -->
    <div
      v-if="!panelCollapsed"
      class="absolute bottom-3 left-3 top-16 z-10 flex w-64 md:w-72 flex-col rounded-lg border border-note bg-note-glass shadow-note backdrop-blur-md"
    >
      <!-- 面板头: 标题 + 新增图层 + 收起 -->
      <div flex items-center gap-2 border-b border-note px-3 py-2 shrink-0>
        <span text-sm font-bold text-note>🗂️ 图层</span>
        <el-button link type="primary" size="small" :icon="Plus" @click="handleAddLayer">
          新增
        </el-button>
        <el-button link size="small" class="ml-auto" :icon="Fold" title="收起面板" @click="panelCollapsed = true" />
      </div>

      <!-- 要素名称过滤 -->
      <div px-2 pt-2 shrink-0>
        <el-input v-model="featureKeyword" size="small" clearable :prefix-icon="Search" placeholder="筛选要素名称" />
      </div>

      <!-- 图层树(图层行 + 展开的要素列表) -->
      <el-scrollbar flex-1 min-h-0>
        <div px-1.5 py-1.5>
          <div v-for="layer in layerStore.layers" :key="layer.id">
            <!-- 图层行: 展开/显隐/激活/统计/删除 -->
            <div
              flex items-center gap-1 rounded px-1 py-1
              :class="isDrawableLayer(layer.id) && layerStore.activeLayerId === layer.id ? 'bg-note-tint' : ''"
            >
              <el-icon
                v-if="isDrawableLayer(layer.id)"
                class="shrink-0 cursor-pointer text-xs text-note-sub transition-transform"
                :class="layerExpanded(layer.id) ? 'rotate-90' : ''"
                @click="toggleLayerExpand(layer.id)"
              >
                <CaretRight />
              </el-icon>
              <span @click.stop>
                <el-switch
                  size="small"
                  :model-value="layerStore.isVisible(layer.id)"
                  @update:model-value="(v: string | number | boolean) => layerStore.setVisible(layer.id, !!v)"
                />
              </span>
              <!-- 点击图层名设为绘制目标(world 除外) -->
              <span
                text-sm truncate
                :class="isDrawableLayer(layer.id) ? 'cursor-pointer text-note' : 'text-note-sub'"
                :title="isDrawableLayer(layer.id) ? '点击设为绘制目标图层' : '内置图层'"
                @click="isDrawableLayer(layer.id) && (layerStore.activeLayerId = layer.id)"
              >
                {{ layer.name }}
              </span>
              <el-tag v-if="layerStore.activeLayerId === layer.id && isDrawableLayer(layer.id)" size="small" type="success" effect="plain" shrink-0>
                绘制中
              </el-tag>
              <span text-xs text-note-sub ml-auto shrink-0>
                {{ layer.id === WORLD_LAYER_ID ? '内置' : layerFeatureCount(layer.id) }}
              </span>
              <el-button
                v-if="isDrawableLayer(layer.id) && layer.id !== DEFAULT_LAYER_ID"
                link type="danger" size="small" :icon="Delete"
                :disabled="layerFeatureCount(layer.id) > 0"
                @click="handleRemoveLayer(layer.id)"
              />
            </div>

            <!-- 要素列表(点击定位, 悬浮显示操作按钮) -->
            <div v-if="isDrawableLayer(layer.id) && layerExpanded(layer.id)">
              <div
                v-for="f in featuresOfLayer(layer.id)"
                :key="f.id"
                class="group flex cursor-pointer items-center gap-1.5 rounded py-1 pl-6 pr-1 hover:bg-note-tint"
                @click="handleFocus(f)"
              >
                <span
                  shrink-0 inline-block w-2.5 h-2.5 rounded-full border border-note
                  :style="{ backgroundColor: resolveStyle(f.feature_type, f.style).color }"
                />
                <span text-xs text-note truncate flex-1>{{ f.name }}</span>
                <!-- 立体物标记(面要素拉伸后 feature_type 仍为 polygon, 以 style.height 区分) -->
                <el-tag v-if="is3D(f)" size="small" type="warning" effect="plain" shrink-0>3D</el-tag>
                <div class="hidden items-center group-hover:flex">
                  <el-button link type="primary" size="small" :icon="Aim" title="定位" @click.stop="handleFocus(f)" />
                  <el-button link type="primary" size="small" :icon="Brush" title="样式" @click.stop="handleStyle(f)" />
                  <el-button link type="primary" size="small" :icon="Edit" title="重命名" @click.stop="handleRename(f)" />
                  <el-button link type="danger" size="small" :icon="Delete" title="删除" @click.stop="handleDelete(f)" />
                </div>
              </div>
              <div v-if="!featuresOfLayer(layer.id).length" py-0.5 pl-6 pr-1 text-xs text-note-sub>
                {{ featureKeyword.trim() ? '无匹配要素' : '暂无要素' }}
              </div>
            </div>
          </div>
        </div>
      </el-scrollbar>

      <p shrink-0 border-t border-note px-3 py-1.5 text-xs text-note-sub>
        绘制目标: {{ activeLayerName }} · 显隐设置自动保存
      </p>
    </div>
    <!-- 面板收起时的展开按钮 -->
    <el-button
      v-else
      class="absolute left-3 top-16 z-10"
      circle :icon="Expand" title="展开图层面板"
      @click="panelCollapsed = false"
    />

    <!-- 指针所指地表坐标(绘制模式下实时显示) -->
    <div
      v-if="hoverLngLat"
      class="absolute bottom-3 right-3 z-10 rounded-full border border-note bg-note-glass px-3 py-1.5 text-xs text-note-sub shadow-note backdrop-blur-md"
    >
      经度 {{ hoverLngLat.lon.toFixed(2) }}° · 纬度 {{ hoverLngLat.lat.toFixed(2) }}°
    </div>

    <!-- 保存要素命名对话框 -->
    <el-dialog v-model="saveDialogVisible" title="保存要素" width="90%" class="max-w-[480px]">
      <el-form :model="saveForm" ref="saveFormRef" :rules="saveRules" label-width="80px">
        <el-form-item label="类型">
          <el-tag :type="tagType(pendingType)">
            {{ featureTypeLabel(pendingType) }}
          </el-tag>
        </el-form-item>
        <el-form-item label="图层">
          <el-select v-model="saveForm.layer" w-full>
            <el-option
              v-for="l in drawableLayers"
              :key="l.id"
              :label="l.name"
              :value="l.id"
            />
          </el-select>
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
import {
  Aim, Box, Brush, CaretRight, Delete, Edit, Expand, Fold,
  Grid, Location, Plus, Pointer, Search, Share,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import {
  createGeoFeature,
  deleteGeoFeature,
  listAllGeoFeatures,
  updateGeoFeature,
} from '../api/feature'
import {
  DEFAULT_LAYER_ID,
  WORLD_LAYER_ID,
  defaultExtrudeStyle,
  defaultFeatureStyles,
  featureLayerOf,
  FeatureType,
  featureTypeOptions,
  featureTypeTagType,
  resolveStyle,
  type GeoFeature,
  type GeoFeatureStyle,
  type GeoJSONGeometry,
  type LngLat,
} from '../types'
import { useLayerStore } from '../stores/layer'
import { SysSettingStore } from '@/common/stores/sys'
import { EarthScene, type DrawMode, type DrawEvent } from '../utils/EarthScene'

// ################ 地球场景 ################
let earthScene: EarthScene | undefined
/** 图层设置 store(显隐/激活图层持久化) */
const layerStore = useLayerStore()
/** 当前绘制模式 */
const drawMode = ref<DrawMode>('none')
/** 绘制中已收集的点(用于完成按钮禁用判断) */
const draftPoints = ref<LngLat[]>([])
/** 绘制模式下指针所指地表坐标(实时显示) */
const hoverLngLat = ref<LngLat | null>(null)
/** 图层面板收起状态(移动端默认收起, 避免遮挡三维视图) */
const { sysStyle } = SysSettingStore()
const panelCollapsed = ref(!sysStyle.isMd)

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

/** 工具栏提示文本(画点=操作提示; 线/面/立体=已选点数与保存目标) */
const toolbarTips = computed(() => {
  if (drawMode.value === 'point') return drawTips.value
  return `已选 ${draftPoints.value.length} 点(单击加点, 双击结束, Ctrl+Z 撤销) · 保存到「${activeLayerName.value}」`
})

/** 初始化场景与全量渲染 */
const initScene = () => {
  earthScene = new EarthScene('earthDom')
  earthScene.observeResize('earthCanvasP')
  // 初始同步图层显隐(持久化恢复的设置要立即作用于渲染, watch 仅监听后续变化)
  for (const l of layerStore.layers) {
    earthScene.setLayerVisible(l.id, layerStore.isVisible(l.id))
  }
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
    // 按类型初始化默认样式(立体物使用拉伸默认样式, 预览实时同步); 图层默认为当前激活图层
    saveForm.value.style = e.mode === 'extrude'
      ? { ...defaultExtrudeStyle }
      : { ...defaultFeatureStyles[e.mode as FeatureType] }
    saveForm.value.layer = layerStore.activeLayerId
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

// ################ 图层管理 ################
/** 全部要素(供图层面板按图层分组展示) */
const allFeatures = ref<GeoFeature[]>([])
/** 可作为绘制目标的图层(world 为内置散点层, 不可绘制) */
const drawableLayers = computed(() =>
  layerStore.layers.filter(l => isDrawableLayer(l.id)),
)
/** 绘制目标图层显示名 */
const activeLayerName = computed(() =>
  drawableLayers.value.find(l => l.id === layerStore.activeLayerId)?.name ?? '默认图层',
)
/** 要素名称过滤关键字 */
const featureKeyword = ref('')
/** 图层展开状态(未记录默认展开) */
const expandedMap = ref<Record<string, boolean>>({})

/** 是否可作为绘制目标图层(world 内置散点层除外) */
const isDrawableLayer = (id: string) => id !== WORLD_LAYER_ID

/** 图层是否展开 */
const layerExpanded = (id: string) => expandedMap.value[id] ?? true

/** 切换图层展开/收起 */
const toggleLayerExpand = (id: string) => {
  expandedMap.value[id] = !layerExpanded(id)
}

/** 图层要素数统计 */
const layerFeatureCount = (id: string) =>
  allFeatures.value.filter(f => featureLayerOf(f) === id).length

/** 图层内要素列表(按名称关键字过滤, 供树形面板展示) */
const featuresOfLayer = (id: string) => {
  const kw = featureKeyword.value.trim().toLowerCase()
  return allFeatures.value.filter((f) => {
    if (featureLayerOf(f) !== id) return false
    return !kw || f.name.toLowerCase().includes(kw)
  })
}

/** 是否立体物(面要素拉伸后以 style.height 区分) */
const is3D = (f: GeoFeature) => (f.style?.height ?? 0) > 0

/** 新增用户图层(成功后自动设为绘制目标) */
const handleAddLayer = () => {
  ElMessageBox.prompt('请输入图层名称', '新增图层', {
    confirmButtonText: '创建',
    cancelButtonText: '取消',
    inputPattern: /\S+/,
    inputErrorMessage: '图层名称不能为空',
  })
    .then(({ value }) => {
      const layer = layerStore.addLayer(value ?? '')
      if (!layer) {
        ElMessage.warning('图层名称已存在')
        return
      }
      ElMessage.success(`图层「${layer.name}」已创建, 新绘制的要素将保存到该图层`)
    })
    .catch(() => {})
}

/** 删除空的用户图层(有要素时后端数据会失去归属, 故仅允许删空层) */
const handleRemoveLayer = (id: string) => {
  if (layerFeatureCount(id) > 0) {
    ElMessage.warning('图层内仍有要素, 请先删除或移动后再删除图层')
    return
  }
  layerStore.removeLayer(id, true)
}

// 图层显隐变化同步到地球渲染
watch(
  () => layerStore.hiddenIds,
  () => {
    for (const l of layerStore.layers) {
      earthScene?.setLayerVisible(l.id, layerStore.isVisible(l.id))
    }
  },
  { deep: true },
)

// ################ 保存对话框 ################
const saveDialogVisible = ref(false)
const saveFormRef = ref<FormInstance>()
const saveForm = ref<{ name: string, layer: string, style: Required<GeoFeatureStyle> }>({
  name: '',
  layer: DEFAULT_LAYER_ID,
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
      // 图层归属存于 properties.layer(后端 JSONB 透传, 无需迁移)
      properties: { layer: saveForm.value.layer || DEFAULT_LAYER_ID },
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

// ################ 数据刷新 ################
/** 拉取全部要素并重渲染地球(图层面板与渲染共用同一份数据) */
const refreshAll = async () => {
  try {
    const all = await listAllGeoFeatures()
    allFeatures.value = all
    earthScene?.renderFeatures(all)
  }
  catch (error) {
    console.error('刷新地球渲染失败:', error)
  }
}

// ################ 要素操作 ################
/** 类型中文标签 */
const featureTypeLabel = (type: string) =>
  featureTypeOptions.find(o => o.value === type)?.label ?? type

/** 类型标签样式(容错返回 info) */
type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'
const tagType = (type: string): TagType =>
  (featureTypeTagType as Record<string, TagType>)[type] ?? 'info'

/** 定位要素(相机飞行聚焦) */
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
    await refreshAll()
  }
  catch (error) {
    console.error('重命名失败:', error)
    ElMessage.error('重命名失败')
  }
  finally {
    submitting.value = false
  }
}

/** 样式编辑(保存后重渲染) */
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
    ElMessage.success('样式已更新')
    styleDialogVisible.value = false
    await refreshAll()
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
        ElMessage.success('删除成功')
        await refreshAll()
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
