/** 数字花园演示组件的共享类型 */

/** 时间轴条目 */
export interface TimelineItem {
  /** 阶段名(节点旁的高亮小标题) */
  phase: string
  /** 描述文本 */
  text: string
}

/** 目录条目 */
export interface TocItem {
  /** 目标区块元素 id */
  id: string
  /** 目录显示文本 */
  label: string
}

/** 目录分组(区块较多时按技巧类别折叠显示) */
export interface TocGroup {
  /** 分组名 */
  label: string
  /** 组内条目 */
  items: TocItem[]
}
