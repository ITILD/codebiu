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
}

/** 更新几何要素请求体(字段可选) */
interface GeoFeatureUpdate {
  name?: string
  geometry?: GeoJSONGeometry
  properties?: Record<string, unknown> | null
}

export {
  FeatureType,
  featureTypeOptions,
  featureTypeTagType,
  type GeoJSONGeometry,
  type LngLat,
  type GeoFeatureBase,
  type GeoFeature,
  type GeoFeatureCreate,
  type GeoFeatureUpdate,
}
