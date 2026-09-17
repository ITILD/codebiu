// 数据库管理 API（后端 module_main：/db，只读）
import { http_base_server } from '@/common/api/http'

/** 数据表元数据 */
export interface DbTableInfo {
  /** 表名 */
  name: string
  /** 表注释 */
  comment: string | null
  /** 列数量 */
  column_count: number
  /** 数据条数 */
  row_count: number
  /** 最后数据更新时间（ISO 字符串，无时间字段或空表时为 null） */
  last_updated: string | null
}

/** 向量库表元数据 */
export interface DbVectorTableInfo {
  /** 表名 */
  name: string
  /** 字段数(注册模型缺失时为 null) */
  field_count: number | null
  /** 向量维度(如 1024) */
  vector_dims: string | null
  /** 数据条数(统计失败时为 null) */
  row_count: number | null
}

/** 向量数据库信息 */
export interface DbVectorInfo {
  /** 实现类型(未启用时为 null) */
  type: string | null
  tables: DbVectorTableInfo[]
}

/** 缓存数据库(Redis)信息 */
export interface DbCacheInfo {
  /** 实现类型(未启用时为 null) */
  type: string | null
  /** 键数量 */
  dbsize?: number
  redis_version?: string | null
  used_memory_human?: string | null
  maxmemory_human?: string | null
  connected_clients?: number | null
  uptime_in_days?: number | null
  keyspace_hits?: number
  keyspace_misses?: number
  /** 命中率(%) */
  hit_rate?: number | null
  /** 查询异常信息 */
  error?: string
}

/** 图数据库信息(由各实现自述的键值对) */
export interface DbGraphInfo {
  /** 实现类型(未启用时为 null) */
  type: string | null
  [key: string]: unknown
}

/** 查看所有数据表（支持按表名/注释关键字过滤） */
export const listDbTables = (keyword?: string) => {
  return http_base_server.get<DbTableInfo[]>('/db/tables', {
    params: { keyword: keyword || undefined },
  })
}

/** 查看向量数据库表清单 */
export const listVectorTables = () => {
  return http_base_server.get<DbVectorInfo>('/db/vector')
}

/** 查看缓存数据库(Redis)运行信息 */
export const getCacheInfo = () => {
  return http_base_server.get<DbCacheInfo>('/db/cache')
}

/** 查看图数据库运行信息 */
export const getGraphInfo = () => {
  return http_base_server.get<DbGraphInfo>('/db/graph')
}
