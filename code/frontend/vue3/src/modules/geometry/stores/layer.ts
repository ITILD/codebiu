/**
 * 地球绘制图层设置(Pinia 持久化)
 *
 * 图层模型:
 *  - world 内置图层: 全球边界散点(由内置 GeoJSON 实时采样, 不可删除)
 *  - default 内置图层: 未分组要素(properties.layer 缺省时归属此层, 不可删除)
 *  - 用户图层: 页面中添加, 绘制时选中的要素归属当前激活图层
 * 显隐开关与激活图层持久化到 localStorage, 刷新后恢复。
 */
import { defineStore } from 'pinia'
import { DEFAULT_LAYER_ID, WORLD_LAYER_ID } from '../types'

/** 图层定义(id 即存储标识, name 为显示名) */
export interface GeoLayer {
  id: string
  name: string
}

/** 内置图层(不可删除) */
const BUILTIN_LAYERS: GeoLayer[] = [
  { id: WORLD_LAYER_ID, name: '全球边界' },
  { id: DEFAULT_LAYER_ID, name: '默认图层' },
]

const useLayerStore = defineStore(
  'geometry-layer',
  () => {
    /** 全部图层(内置 + 用户) */
    const layers = ref<GeoLayer[]>([...BUILTIN_LAYERS])
    /** 隐藏的图层ID列表 */
    const hiddenIds = ref<string[]>([])
    /** 绘制时要素归属的激活图层(不能是 world) */
    const activeLayerId = ref<string>(DEFAULT_LAYER_ID)

    /** 图层是否可见 */
    const isVisible = (id: string) => !hiddenIds.value.includes(id)

    /** 切换图层显隐 */
    const setVisible = (id: string, visible: boolean) => {
      hiddenIds.value = visible
        ? hiddenIds.value.filter(v => v !== id)
        : [...new Set([...hiddenIds.value, id])]
    }

    /** 新增用户图层(同名拒绝, 返回 null) */
    const addLayer = (name: string): GeoLayer | null => {
      const trimmed = name.trim()
      if (!trimmed) return null
      if (layers.value.some(l => l.name === trimmed)) return null
      const layer: GeoLayer = { id: `layer_${Date.now().toString(36)}`, name: trimmed }
      layers.value = [...layers.value, layer]
      activeLayerId.value = layer.id
      return layer
    }

    /** 删除用户图层(仅允许删除无要素的空图层, 内置图层不可删) */
    const removeLayer = (id: string, isEmpty: boolean): boolean => {
      if (id === WORLD_LAYER_ID || id === DEFAULT_LAYER_ID) return false
      if (!isEmpty) return false
      layers.value = layers.value.filter(l => l.id !== id)
      if (activeLayerId.value === id) activeLayerId.value = DEFAULT_LAYER_ID
      hiddenIds.value = hiddenIds.value.filter(v => v !== id)
      return true
    }

    return { layers, hiddenIds, activeLayerId, isVisible, setVisible, addLayer, removeLayer }
  },
  { persist: true },
)

export { useLayerStore }
