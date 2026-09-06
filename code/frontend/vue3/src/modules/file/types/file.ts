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
  /** 来源模块标记(rag/avatar 等业务条目; NULL=文件管理自有条目, 业务条目只读) */
  source_module: string | null;
  file_size_bytes: number | null;
  file_extension: string | null;
  mime_type: string | null;
  description: string | null;
  /** 关键词标签组(默认空,可手动输入或由RAG智能提取) */
  tags: string[] | null;
  is_active: boolean;
  user_id: string | null;
  group_id: string | null;
  entry_status: EntryStatus | null;
  created_at: string;
  updated_at: string;
};

/** 条目更新参数(名称/描述/标签可改) */
type FileEntryUpdate = {
  name?: string;
  description?: string;
  tags?: string[];
};

/** 条目详情(内容元数据+上传用户名) */
type FileEntryDetail = FileEntry & {
  /** 物理存储相对位置(仅文件) */
  physical_storage: string | null;
  /** 内容引用计数(仅文件) */
  ref_count: number | null;
  /** 物理存储类型(local/s3/rustfs, 仅文件) */
  storage_type: string | null;
  /** 内容状态(仅文件) */
  content_status: EntryStatus | null;
  /** 上传用户名(昵称优先) */
  owner_name: string | null;
};

/** 批量删除结果 */
type BatchDeleteResult = {
  /** 成功删除数 */
  deleted: number;
  /** 失败明细 */
  failed: { id: string; error: string }[];
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
  FileEntryDetail,
  BatchDeleteResult,
  StorageStats,
  MigrateRequest,
  MigrateResult,
};
