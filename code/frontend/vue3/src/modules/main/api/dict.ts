// src/modules/main/api/dict.ts
// 字段表(字典类型/字典项)接口(对应后端 /dict_types 与 /dict_items)
import { http_base_server } from '@/common/api/http';
import type { PaginationParams, PaginationResponse } from '@/common/types/common';
import type {
  DictType,
  DictTypeCreate,
  DictTypeUpdate,
  DictItem,
  DictItemCreate,
  DictItemUpdate,
} from '../types/dict';

// ################################################## 字典类型
/** 创建字典类型 */
export const createDictType = (data: DictTypeCreate) => {
  return http_base_server.post<string>('/dict_types', data);
};

/** 字典类型列表过滤参数(type 别名具有隐式索引签名, 可直接传给 http 层) */
export type DictTypeListParams = PaginationParams & {
  /** 类型名称/编码模糊搜索 */
  keyword?: string;
  /** 状态过滤(true=启用/false=禁用) */
  is_active?: boolean;
}

/** 分页查询字典类型列表(支持名称/编码模糊搜索与状态过滤) */
export const listDictTypes = (params: DictTypeListParams) => {
  return http_base_server.get<PaginationResponse<DictType>>('/dict_types/list', { params });
};

/** 根据编码获取字典类型 */
export const getDictTypeByCode = (typeCode: string) => {
  return http_base_server.get<DictType>(`/dict_types/code/${typeCode}`);
};

/** 获取单个字典类型详情 */
export const getDictType = (typeId: string) => {
  return http_base_server.get<DictType>(`/dict_types/${typeId}`);
};

/** 更新字典类型 */
export const updateDictType = (typeId: string, data: DictTypeUpdate) => {
  return http_base_server.put<void>(`/dict_types/${typeId}`, data);
};

/** 删除字典类型 */
export const deleteDictType = (typeId: string) => {
  return http_base_server.delete<void>(`/dict_types/${typeId}`);
};

// ################################################## 字典项
/** 创建字典项 */
export const createDictItem = (data: DictItemCreate) => {
  return http_base_server.post<string>('/dict_items', data);
};

/** 分页查询字典项列表 */
export const listDictItems = (params: PaginationParams) => {
  return http_base_server.get<PaginationResponse<DictItem>>('/dict_items/list', { params });
};

/** 根据字典类型编码查询字典项列表 */
export const listDictItemsByType = (typeCode: string) => {
  return http_base_server.get<DictItem[]>(`/dict_items/by-type/${typeCode}`);
};

/** 根据字典类型统计字典项数量 */
export const countDictItemsByType = (typeCode: string) => {
  return http_base_server.get<number>(`/dict_items/by-type/${typeCode}/count`);
};

/** 根据编码获取字典项 */
export const getDictItemByCode = (itemCode: string) => {
  return http_base_server.get<DictItem>(`/dict_items/code/${itemCode}`);
};

/** 获取单个字典项详情 */
export const getDictItem = (itemId: string) => {
  return http_base_server.get<DictItem>(`/dict_items/${itemId}`);
};

/** 更新字典项 */
export const updateDictItem = (itemId: string, data: DictItemUpdate) => {
  return http_base_server.put<void>(`/dict_items/${itemId}`, data);
};

/** 删除字典项 */
export const deleteDictItem = (itemId: string) => {
  return http_base_server.delete<void>(`/dict_items/${itemId}`);
};
