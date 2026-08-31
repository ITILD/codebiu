// 地理空间模块 API(Babylon 地球绘制的点线面要素管理)
import { http_base_server } from '@/utils/http'
import type { PaginationParams, PaginationResponse } from '@/types/common'
import type { GeoFeature, GeoFeatureCreate, GeoFeatureUpdate } from '@/types/geometry'

/** 要素列表过滤参数 */
export type GeoFeatureListParams = PaginationParams & {
  /** 要素名称模糊搜索 */
  keyword?: string
  /** 几何类型过滤(point/linestring/polygon) */
  feature_type?: string
}

/**
 * 分页查询几何要素列表(支持名称/类型多字段过滤)
 * @param params 分页与过滤参数
 */
export const listGeoFeatures = (params: GeoFeatureListParams) => {
  return http_base_server.get<PaginationResponse<GeoFeature>>(
    '/geometry/features/list',
    { params },
  )
}

/**
 * 查询全部几何要素(不分页, 供地球场景一次性渲染)
 */
export const listAllGeoFeatures = () => {
  return http_base_server.get<GeoFeature[]>('/geometry/features/all')
}

/**
 * 创建几何要素(以 GeoJSON 提交点/线/面)
 * @param data 要素数据(名称 + 几何体)
 */
export const createGeoFeature = (data: GeoFeatureCreate) => {
  return http_base_server.post<string>('/geometry/features', data)
}

/**
 * 更新几何要素(重命名/重绘几何体)
 * @param id 要素ID
 * @param data 更新数据(字段可选)
 */
export const updateGeoFeature = (id: string, data: GeoFeatureUpdate) => {
  return http_base_server.put<void>(`/geometry/features/${id}`, data)
}

/**
 * 删除几何要素
 * @param id 要素ID
 */
export const deleteGeoFeature = (id: string) => {
  return http_base_server.delete<void>(`/geometry/features/${id}`)
}
