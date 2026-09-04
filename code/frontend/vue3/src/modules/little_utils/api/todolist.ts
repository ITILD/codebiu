// src/modules/little_utils/api/todolist.ts
import { http_base_server } from '@/common/api/http';
import {
  type InfiniteScrollParams,
  type InfiniteScrollResponse,
  type PaginationParams,
  type PaginationResponse,
} from '@/common/types/common';
import type { Todolist, TodolistCreate, TodolistUpdate } from '../types/todolist';

/**
 * 创建新模板
 * @param todolist 模板数据
 * @returns 创建的模板ID
 */
export const createTodolist = (todolist: TodolistCreate) => {
  return http_base_server.post<object>('/little-utils/todolists', todolist);
};

/**
 * 删除模板
 * @param todolistId 模板ID
 */
export const deleteTodolist = (todolistId: string) => {
  return http_base_server.delete<void>(`/little-utils/todolists/${todolistId}`);
};

/**
 * 更新模板
 * @param todolistId 模板ID
 * @param todolist 模板数据
 */
export const updateTodolist = (todolistId: string, todolist: TodolistUpdate) => {
  return http_base_server.put<void>(`/little-utils/todolists/${todolistId}`, todolist);
};

/**
 * 获取单个模板详情
 * @param todolistId 模板ID
 * @returns 模板详情
 */
export const getTodolist = (todolistId: string) => {
  return http_base_server.get<Todolist>(`/little-utils/todolists/${todolistId}`);
};

/**
 * 分页查询模板列表
 * @param params 分页参数
 * @returns 分页响应结果
 */
export const listTodolists = (params: PaginationParams) => {
  return http_base_server.get<PaginationResponse<Todolist>>('/little-utils/todolists/list', { params });
};

/**
 * 无限滚动加载模板列表
 * @param params 滚动加载参数
 * @returns 滚动加载响应结果
 */
export const infiniteScrollTodolists = (params: InfiniteScrollParams) => {
  return http_base_server.get<InfiniteScrollResponse<Todolist>>('/little-utils/todolists/scroll', {
    params
  });
};
