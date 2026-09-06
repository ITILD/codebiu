// src/modules/site/api/todolist.ts —— 备忘接口(/site/todolists)
import { http_base_server } from '@/common/api/http'
import type { PaginationParams, PaginationResponse } from '@/common/types/common'
import type { Todolist, TodolistCreate, TodolistUpdate } from '../types/todolist'

/** 备忘列表查询参数(分页 + 过滤) */
export interface ListMemosParams extends PaginationParams {
  /** 备忘标题模糊搜索 */
  name?: string
  /** 状态过滤(todo/done/pause) */
  status?: string
}

/** 创建备忘(归属当前用户, start_at 为日历展示时间) */
export const createTodolist = (todolist: TodolistCreate) => {
  return http_base_server.post<string>('/site/todolists', todolist)
}

/** 删除备忘(仅本人) */
export const deleteTodolist = (todolistId: string) => {
  return http_base_server.delete<void>(`/site/todolists/${todolistId}`)
}

/** 更新备忘(标题/内容/时间/状态等) */
export const updateTodolist = (todolistId: string, todolist: TodolistUpdate) => {
  return http_base_server.put<void>(`/site/todolists/${todolistId}`, todolist)
}

/** 获取备忘详情(仅本人可见) */
export const getTodolist = (todolistId: string) => {
  return http_base_server.get<Todolist>(`/site/todolists/${todolistId}`)
}

/** 分页查询备忘列表(管理页) */
export const listTodolists = (params: ListMemosParams) => {
  return http_base_server.get<PaginationResponse<Todolist>>('/site/todolists/list', { params })
}

/**
 * 按时间范围查询备忘(日历 年/月/周 视图数据源)
 * @param start 范围起始(含, ISO 带时区)
 * @param end 范围结束(不含, ISO 带时区)
 */
export const listMemosByRange = (start: string, end: string) => {
  return http_base_server.get<Todolist[]>('/site/todolists/range', {
    params: { start, end },
  })
}
