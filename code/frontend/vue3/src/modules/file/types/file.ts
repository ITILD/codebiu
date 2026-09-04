// src/types/file.ts
// 文件模块类型定义(虚拟文件系统)

/** 条目状态 */
enum EntryStatus {
  PENDING = "pending",
  RUNNING = "running",
  SUCCESS = "success",
  FAILED = "failed",
}

/** 文件/目录条目(虚拟文件系统) */
type FileEntry = {
  id: string;
  pid: string | null;
  /** 条目名称(文件名或目录名) */
  name: string;
  /** 逻辑路径(用户视角) */
  logical_path: string;
  is_directory: boolean;
  /** 内容哈希(仅文件) */
  content_hash: string | null;
  file_size_bytes: number | null;
  file_extension: string | null;
  mime_type: string | null;
  description: string | null;
  is_active: boolean;
  user_id: string | null;
  group_id: string | null;
  entry_status: EntryStatus | null;
  created_at: string;
  updated_at: string;
};

/** 条目更新参数(仅名称/描述可改) */
type FileEntryUpdate = {
  name?: string;
  description?: string;
};

export { EntryStatus };
export type { FileEntry, FileEntryUpdate };
