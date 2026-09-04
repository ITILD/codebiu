// src/modules/main/types/dict.ts
// 对应后端 module_main 的 /dict_types 与 /dict_items 接口数据结构

/** 字典类型(字段表-类型表) */
export type DictType = {
  id: string
  type_code: string // 类型编码
  type_name: string // 类型名称
  description: string | null // 描述
  is_active: boolean // 是否激活
  sort_order: number // 排序顺序
  created_at: string
  updated_at: string
}

/** 创建字典类型请求 */
export type DictTypeCreate = {
  type_code: string
  type_name: string
  description?: string | null
  is_active?: boolean
  sort_order?: number
}

/** 更新字典类型请求 */
export type DictTypeUpdate = DictTypeCreate

/** 字典项(字段表-项表) */
export type DictItem = {
  id: string
  dict_type_id: string // 所属字典类型ID
  item_code: string // 项编码
  item_name: string // 项名称
  item_value: string | null // 项值
  description: string | null // 描述
  is_active: boolean // 是否激活
  sort_order: number // 排序顺序
  created_at: string
  updated_at: string
}

/** 创建字典项请求 */
export type DictItemCreate = {
  dict_type_id: string
  item_code: string
  item_name: string
  item_value?: string | null
  description?: string | null
  is_active?: boolean
  sort_order?: number
}

/** 更新字典项请求 */
export type DictItemUpdate = DictItemCreate
