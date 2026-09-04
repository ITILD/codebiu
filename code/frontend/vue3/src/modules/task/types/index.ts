// 任务队列模块类型定义(Celery + Redis 异步任务)

/** 任务状态(与后端 QueueTaskStatus 对齐) */
type TaskStatus = 'pending' | 'running' | 'success' | 'failed' | 'cancelled' | 'revoked'

/** 状态显示配置(标签文本) */
const statusLabels: Record<TaskStatus, string> = {
  pending: '排队中',
  running: '执行中',
  success: '成功',
  failed: '失败',
  cancelled: '已取消',
  revoked: '已撤销',
}

/** 状态标签样式(element-plus tag type) */
type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'
const statusTagTypes: Record<TaskStatus, TagType> = {
  pending: 'info',
  running: 'primary',
  success: 'success',
  failed: 'danger',
  cancelled: 'warning',
  revoked: 'warning',
}

/** 状态筛选下拉选项 */
const statusOptions = (Object.keys(statusLabels) as TaskStatus[]).map(value => ({
  label: statusLabels[value],
  value,
}))

/** 任务类型定义(后端注册表条目, 供新建任务下拉与默认参数模板) */
interface TaskTypeDef {
  type: string
  name: string
  description: string
  celery_task: string
  default_payload: Record<string, unknown>
}

/** 任务记录(后端返回, 含 Celery 侧状态对照) */
interface QueueTask {
  id: string
  name: string
  task_type: string
  payload: Record<string, unknown>
  priority: number
  status: TaskStatus
  /** 完成百分比 0~100(worker 实时回写) */
  progress: number
  /** 当前执行阶段描述 */
  message: string | null
  result: Record<string, unknown> | null
  error: string | null
  celery_task_id: string | null
  /** Celery 结果后端状态(PENDING/STARTED/PROGRESS/SUCCESS/FAILURE/REVOKED) */
  celery_state: string | null
  /** Celery 侧回传百分比 */
  celery_progress: number | null
  started_at: string | null
  finished_at: string | null
  created_at: string
  updated_at: string
}

/** 创建任务请求体 */
interface QueueTaskCreate {
  name: string
  task_type: string
  payload: Record<string, unknown>
}

/** 任务状态统计(概览卡片) */
interface TaskStats {
  total: number
  pending: number
  running: number
  success: number
  failed: number
  cancelled: number
}

export {
  statusLabels,
  statusTagTypes,
  statusOptions,
  type TagType,
  type TaskStatus,
  type TaskTypeDef,
  type QueueTask,
  type QueueTaskCreate,
  type TaskStats,
}
