// 地理空间模块类型定义(Babylon 地球绘制 + PostGIS 存储)

/** 几何要素类型(与 GeoJSON 类型对齐) */
enum FeatureType {
  POINT = 'point',
  LINESTRING = 'linestring',
  POLYGON = 'polygon',
}

/** 几何类型显示配置 */
const featureTypeOptions: { label: string; value: FeatureType }[] = [
  { label: '点', value: FeatureType.POINT },
  { label: '线', value: FeatureType.LINESTRING },
  { label: '面', value: FeatureType.POLYGON },
]

/** 几何类型标签样式(element-plus tag type) */
const featureTypeTagType: Record<FeatureType, string> = {
  [FeatureType.POINT]: 'danger',
  [FeatureType.LINESTRING]: 'primary',
  [FeatureType.POLYGON]: 'success',
}

/** 要素渲染样式(以 JSON 存储于数据库 style 字段) */
interface GeoFeatureStyle {
  /** 主色(HEX, 如 '#e0564d') */
  color?: string
  /** 透明度 0~1(点/线整体, 面为填充透明度) */
  opacity?: number
  /** 粗细系数 0.5~3(点=标记大小, 线=线宽, 面=描边宽度) */
  width?: number
  /** 拉伸高度(球面单位, >0 时面渲染为立体棱柱, 0 为平面) */
  height?: number
}

/** 各要素类型的默认样式(卡通风格: 高饱和暖色 + 加粗) */
const defaultFeatureStyles: Record<FeatureType, Required<GeoFeatureStyle>> = {
  [FeatureType.POINT]: { color: '#ff6b6b', opacity: 1, width: 1.5, height: 0 },
  [FeatureType.LINESTRING]: { color: '#ff922b', opacity: 1, width: 1.5, height: 0 },
  [FeatureType.POLYGON]: { color: '#ffd43b', opacity: 0.5, width: 1.5, height: 0 },
}

/** 立体物默认样式(面拉伸为棱柱, 高度相对球面) */
const defaultExtrudeStyle: Required<GeoFeatureStyle> = {
  color: '#f06595', opacity: 1, width: 1.5, height: 0.08,
}

/** 取要素样式(合并默认值, 兼容无 style 的历史数据) */
const resolveStyle = (featureType: string, style?: GeoFeatureStyle | null): Required<GeoFeatureStyle> => {
  const base = defaultFeatureStyles[featureType as FeatureType] ?? defaultFeatureStyles[FeatureType.POINT]
  return { ...base, ...(style ?? {}) }
}

/** GeoJSON 几何体(点/线/面) */
interface GeoJSONGeometry {
  type: 'Point' | 'LineString' | 'Polygon'
  /** [lon, lat] | [[lon,lat],...] | [[[lon,lat],...],...] */
  coordinates: number[] | number[][] | number[][][]
}

/** 经纬度坐标 */
interface LngLat {
  lon: number
  lat: number
}

/** 几何要素基础字段 */
interface GeoFeatureBase {
  name: string
  feature_type: FeatureType
  properties?: Record<string, unknown> | null
  style?: GeoFeatureStyle | null
}

/** 几何要素(后端返回, geometry 为 GeoJSON) */
interface GeoFeature extends GeoFeatureBase {
  id: string
  user_id: string
  geometry: GeoJSONGeometry
  created_at: string // ISO格式日期字符串
  updated_at: string // ISO格式日期字符串
}

/** 创建几何要素请求体 */
interface GeoFeatureCreate {
  name: string
  geometry: GeoJSONGeometry
  properties?: Record<string, unknown> | null
  style?: GeoFeatureStyle | null
}

/** 更新几何要素请求体(字段可选) */
interface GeoFeatureUpdate {
  name?: string
  geometry?: GeoJSONGeometry
  properties?: Record<string, unknown> | null
  style?: GeoFeatureStyle | null
}

export {
  FeatureType,
  featureTypeOptions,
  featureTypeTagType,
  defaultFeatureStyles,
  defaultExtrudeStyle,
  resolveStyle,
  type GeoFeatureStyle,
  type GeoJSONGeometry,
  type LngLat,
  type GeoFeatureBase,
  type GeoFeature,
  type GeoFeatureCreate,
  type GeoFeatureUpdate,
}
