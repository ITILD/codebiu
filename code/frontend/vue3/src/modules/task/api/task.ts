// 任务队列模块 API(Celery+Redis 异步任务管理)
import { http_base_server } from '@/common/api/http'
import type { PaginationParams, PaginationResponse } from '@/common/types/common'
import type { QueueTask, QueueTaskCreate, TaskStats, TaskTypeDef } from '../types'

/** 任务列表过滤参数 */
export type TaskListParams = PaginationParams & {
  /** 任务名称模糊搜索 */
  keyword?: string
  /** 状态过滤(pending/running/success/failed/cancelled) */
  status?: string
  /** 任务类型过滤 */
  task_type?: string
}

/**
 * 查询任务类型注册表(新建任务下拉 + 默认参数模板)
 */
export const getTaskRegistry = () => {
  return http_base_server.get<TaskTypeDef[]>('/task/tasks/registry')
}

/**
 * 任务状态统计(概览卡片, 轮询刷新)
 */
export const getTaskStats = () => {
  return http_base_server.get<TaskStats>('/task/tasks/stats')
}

/**
 * 分页查询任务列表(含 Celery 状态对照字段)
 * @param params 分页与过滤参数
 */
export const listTasks = (params: TaskListParams) => {
  return http_base_server.get<PaginationResponse<QueueTask>>('/task/tasks/list', { params })
}

/**
 * 查询任务详情(含 Celery 侧状态/百分比)
 * @param id 任务ID
 */
export const getTask = (id: string) => {
  return http_base_server.get<QueueTask>(`/task/tasks/${id}`)
}

/**
 * 创建任务并投递 Celery 队列
 * @param data 任务数据(名称/类型/参数 JSON)
 */
export const createTask = (data: QueueTaskCreate) => {
  return http_base_server.post<string>('/task/tasks', data)
}

/**
 * 从 Celery 结果后端同步任务状态(worker 回写中断时校正)
 * @param id 任务ID
 */
export const syncTask = (id: string) => {
  return http_base_server.post<QueueTask>(`/task/tasks/${id}/sync`)
}

/**
 * 取消任务(排队/执行中)
 * @param id 任务ID
 */
export const cancelTask = (id: string) => {
  return http_base_server.post<void>(`/task/tasks/${id}/cancel`)
}

/**
 * 重试任务(已结束的任务重新入队)
 * @param id 任务ID
 */
export const retryTask = (id: string) => {
  return http_base_server.post<QueueTask>(`/task/tasks/${id}/retry`)
}

/**
 * 删除任务记录
 * @param id 任务ID
 */
export const deleteTask = (id: string) => {
  return http_base_server.delete<void>(`/task/tasks/${id}`)
}
