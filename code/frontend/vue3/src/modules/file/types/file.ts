// src/modules/file/types/file.ts
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

/** 存储统计信息 */
type StorageStats = {
  /** 当前生效存储类型(local/s3/rustfs) */
  storage_type: string;
  /** 逻辑条目总数(含目录) */
  entry_total: number;
  /** 文件条目数 */
  file_total: number;
  /** 目录条目数 */
  folder_total: number;
  /** 物理内容记录数(去重后) */
  content_total: number;
  /** 物理存储总占用(字节) */
  used_bytes: number;
};

/** 存储迁移请求 */
type MigrateRequest = {
  from_type: "local" | "s3" | "rustfs";
  to_type: "local" | "s3" | "rustfs";
};

/** 存储迁移结果 */
type MigrateResult = {
  total: number;
  migrated: number;
  skipped: number;
  failed: { content_hash: string; error: string }[];
};

export { EntryStatus };
export type {
  FileEntry,
  FileEntryUpdate,
  StorageStats,
  MigrateRequest,
  MigrateResult,
};
