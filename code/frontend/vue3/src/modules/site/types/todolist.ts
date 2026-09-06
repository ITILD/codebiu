// src/modules/site/types/todolist.ts —— 备忘类型(承接原 little_utils/todolist)

/** 备忘状态: 待办 / 完成 / 暂停 */
export type TodoStatus = 'todo' | 'done' | 'pause'

/** 备忘实体(start_at 为日历展示时间) */
export interface Todolist {
  id: string
  pid?: string | null
  /** 备忘标题(日历展示) */
  name: string | null
  /** 备忘全文内容(周视图取前200字) */
  value: string
  description?: string | null
  /** 备忘时间(ISO, 日历归属依据) */
  start_at: string
  end_at?: string | null
  status: TodoStatus
  user_id?: string | null
  created_at: string
  updated_at: string
}

/** 创建备忘参数 */
export interface TodolistCreate {
  name: string
  value?: string
  description?: string | null
  /** 备忘时间(ISO), 缺省为当前时间 */
  start_at?: string
  end_at?: string | null
  status?: TodoStatus
}

/** 更新备忘参数(全部可选, 仅更新传入字段) */
export type TodolistUpdate = Partial<TodolistCreate>
