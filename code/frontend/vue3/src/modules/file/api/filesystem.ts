// src/modules/file/api/filesystem.ts
// 文件模块 API(虚拟文件系统,后端存储可配置切换本地/S3对象存储)
// 上传链路复用公共统一存储流程(common/utils/storageUpload),本模块仅提供端点适配器:
// - direct(s3): 凭证签发(init)后前端预签名直传对象存储,数据面不经过服务端
// - proxy(local): 小文件 FormData 中转 /upload,大文件分片中转
import { http_base_server } from '@/common/api/http';
import { createStorageUploader } from '@/common/utils/storageUpload';
import type { MultipartPart } from '@/common/utils/storageUpload';
import type { PaginationParams, PaginationResponse } from '@/common/types/common';
import type {
  FileEntry,
  FileEntryUpdate,
  StorageStats,
  MigrateRequest,
  MigrateResult,
} from '../types/file';

/** 上传模式缓存(direct=预签名直传 / proxy=服务端中转) */
interface UploadMode {
  mode: 'direct' | 'proxy';
  part_size: number;
  max_size: number;
}
let uploadModeCache: UploadMode | null = null;

/**
 * 查询上传模式(启动后首次调用获取并缓存,决定直传/中转策略)
 */
export const getUploadMode = async (): Promise<UploadMode> => {
  if (!uploadModeCache) {
    uploadModeCache = await http_base_server.get<UploadMode>(
      '/file/filesystem/upload-mode'
    );
  }
  return uploadModeCache;
};

/**
 * 浏览指定目录(目录排前,名称排序)
 * @param pid 父目录ID(为空表示根目录)
 * @param params 分页参数
 * @param name 名称模糊过滤(服务端过滤,为空不过滤)
 */
export const listDir = (
  pid: string | undefined,
  params: PaginationParams,
  name?: string
) => {
  return http_base_server.get<PaginationResponse<FileEntry>>(
    '/file/filesystem/list-dir',
    { params: { pid: pid || undefined, name: name || undefined, ...params } }
  );
};

/**
 * 查询指定目录下的全部子目录(不分页,目录树懒加载用)
 * @param pid 父目录ID(为空表示根目录)
 */
export const listDirs = (pid?: string) => {
  return http_base_server.get<FileEntry[]>('/file/filesystem/dirs', {
    params: { pid: pid || undefined },
  });
};

/**
 * 上传文件到指定目录(按后端上传模式自动分流)
 * - direct(s3): init 签发凭证+预签名URL -> 浏览器直传对象存储 -> complete 对账建条目(秒传时直接建条目)
 * - proxy(local): ≤10MB FormData 中转 /upload;>10MB init -> 分片中转 -> complete
 * @param file 文件对象
 * @param pid 父目录ID(为空上传到根目录)
 * @param description 文件描述
 */
export const uploadFile = (file: File, pid?: string, description?: string) => {
  return fileStorageUploader(file, { pid, description });
};

/** 分片上传初始化(凭证签发阶段完成秒传/去重/校验) */
const initMultipart = (data: {
  filename: string;
  file_size_bytes: number;
  content_hash: string;
  content_type?: string;
  pid?: string;
  description?: string;
}) => {
  return http_base_server.post<MultipartInitResponse>(
    '/file/filesystem/multipart/init',
    data
  );
};

/** proxy 模式分片中转(分片二进制经服务端保存;返回分片信息) */
const uploadMultipartPart = (
  uploadId: string,
  partNumber: number,
  content: ArrayBuffer
) => {
  return http_base_server.putRaw<MultipartPart>(
    `/file/filesystem/multipart/${encodeURIComponent(uploadId)}/parts/${partNumber}`,
    content,
    { headers: { 'Content-Type': 'application/octet-stream' } }
  );
};

/** 完成分片上传(服务端对账分片清单并创建条目) */
const completeMultipart = (
  uploadId: string,
  data: {
    filename: string;
    pid?: string;
    description?: string;
    file_size_bytes: number;
    parts: MultipartPart[];
  }
) => {
  return http_base_server.post<FileEntry>(
    `/file/filesystem/multipart/${encodeURIComponent(uploadId)}/complete`,
    data
  );
};

/** 秒传建条目(内容已存在时直接创建文件记录) */
const completeEntry = (data: {
  name: string;
  pid?: string;
  content_hash: string;
  file_size_bytes: number;
  mime_type?: string;
  description?: string;
}) => {
  return http_base_server.post<FileEntry>('/file/filesystem/upload-complete', data);
};

/** proxy 模式小文件 FormData 中转(≤max_size) */
const uploadFileDirect = (file: File, pid?: string, description?: string) => {
  const formData = new FormData();
  formData.append('file', file);
  if (description) formData.append('description', description);
  return http_base_server.post<FileEntry>(
    '/file/filesystem/upload',
    formData,
    { params: { pid: pid || undefined } }
  );
};

/** 分片上传初始化响应(mode=direct 时 part_urls 与分片号一一对应) */
interface MultipartInitResponse {
  is_existing: boolean;
  upload_id: string | null;
  part_size: number;
  mode: 'direct' | 'proxy';
  part_urls: string[] | null;
}

/** 文件管理统一存储上传器(端点适配器: 记录口径为虚拟文件系统条目) */
const fileStorageUploader = createStorageUploader<
  { pid?: string; description?: string },
  FileEntry
>({
  getMode: getUploadMode,
  init: (file, contentHash, ctx) =>
    initMultipart({
      filename: file.name,
      file_size_bytes: file.size,
      content_hash: contentHash,
      content_type: file.type || undefined,
      pid: ctx?.pid,
      description: ctx?.description,
    }),
  uploadPart: uploadMultipartPart,
  complete: (file, uploadId, parts, ctx) =>
    completeMultipart(uploadId, {
      filename: file.name,
      pid: ctx?.pid,
      description: ctx?.description,
      file_size_bytes: file.size,
      parts,
    }),
  instant: (file, contentHash, ctx) =>
    completeEntry({
      name: file.name,
      pid: ctx?.pid,
      content_hash: contentHash,
      file_size_bytes: file.size,
      mime_type: file.type || undefined,
      description: ctx?.description,
    }),
  smallDirect: (file, ctx) => uploadFileDirect(file, ctx?.pid, ctx?.description),
});

/**
 * 创建目录
 * @param name 目录名称
 * @param pid 父目录ID(为空表示根目录)
 */
export const createFolder = (name: string, pid?: string) => {
  return http_base_server.post<FileEntry>(
    '/file/filesystem/folder',
    null,
    { params: { name, pid: pid || undefined } }
  );
};

/**
 * 获取文件或目录元数据
 * @param entryId 条目ID
 */
export const getFileEntry = (entryId: string) => {
  return http_base_server.get<FileEntry>(`/file/filesystem/entries/${entryId}`);
};

/**
 * 获取文件下载地址(相对后端路径)
 * @param entryId 文件ID
 */
export const getFileDownloadUrl = (entryId: string) => {
  return `/base_server/file/filesystem/download/${entryId}`;
};

/**
 * 更新条目信息(名称变更自动维护路径)
 * @param entryId 条目ID
 * @param data 更新数据
 */
export const updateFileEntry = (entryId: string, data: FileEntryUpdate) => {
  return http_base_server.put<FileEntry>(
    `/file/filesystem/entries/${entryId}`,
    data
  );
};

/**
 * 重命名条目(目录同步更新子树路径)
 * @param entryId 条目ID
 * @param newName 新名称
 */
export const renameEntry = (entryId: string, newName: string) => {
  return http_base_server.put<FileEntry>(
    `/file/filesystem/entries/${entryId}/rename`,
    null,
    { params: { new_name: newName } }
  );
};

/**
 * 移动条目到目标目录(目录同步更新子树路径)
 * @param entryId 条目ID
 * @param targetPid 目标父目录ID(为空表示根目录)
 */
export const moveEntry = (entryId: string, targetPid?: string) => {
  return http_base_server.put<FileEntry>(
    `/file/filesystem/entries/${entryId}/move`,
    null,
    { params: { target_pid: targetPid || undefined } }
  );
};

/**
 * 删除文件
 * @param entryId 文件ID
 */
export const deleteFile = (entryId: string) => {
  return http_base_server.delete<void>(`/file/filesystem/files/${entryId}`);
};

/**
 * 递归删除目录(含全部子项)
 * @param folderId 目录ID
 */
export const deleteFolder = (folderId: string) => {
  return http_base_server.delete<void>(`/file/filesystem/folders/${folderId}`);
};

/**
 * 按逻辑路径查询条目(路径导航用)
 * @param path 逻辑路径(如 /docs/readme.md)
 */
export const getEntryByPath = (path: string) => {
  return http_base_server.get<FileEntry>('/file/filesystem/path', {
    params: { path },
  });
};

/**
 * 按逻辑路径浏览目录(目录排前,名称排序)
 * @param path 目录逻辑路径
 * @param params 分页参数
 * @param name 名称模糊过滤
 */
export const listByPath = (
  path: string,
  params: PaginationParams,
  name?: string
) => {
  return http_base_server.get<PaginationResponse<FileEntry>>(
    '/file/filesystem/list-by-path',
    { params: { path, name: name || undefined, ...params } }
  );
};

/**
 * 按逻辑路径递归创建目录(mkdir -p 语义,已存在直接返回)
 * @param path 目录路径(如 /docs/images,多级一次创建)
 */
export const mkdirP = (path: string) => {
  return http_base_server.post<FileEntry>('/file/filesystem/mkdir-p', null, {
    params: { path },
  });
};

/**
 * 全树模糊搜索条目(匹配名称或逻辑路径)
 * @param keyword 搜索关键字
 * @param params 分页参数
 */
export const searchEntries = (keyword: string, params: PaginationParams) => {
  return http_base_server.get<PaginationResponse<FileEntry>>(
    '/file/filesystem/search',
    { params: { keyword, ...params } }
  );
};

/**
 * 复制条目(文件共享内容哈希,目录递归整树复制)
 * @param entryId 源条目ID
 * @param targetPid 目标父目录ID(为空表示根目录)
 */
export const copyEntry = (entryId: string, targetPid?: string) => {
  return http_base_server.post<FileEntry>('/file/filesystem/copy', null, {
    params: { entry_id: entryId, target_pid: targetPid || undefined },
  });
};

/**
 * 存储统计(条目数/物理内容数/总占用/当前存储类型)
 */
export const getStorageStats = () => {
  return http_base_server.get<StorageStats>('/file/filesystem/stats');
};

/**
 * 存储迁移(local<->s3 物理内容搬运,切换配置前调用)
 * @param data 迁移请求(源/目标存储类型)
 */
export const migrateStorage = (data: MigrateRequest) => {
  return http_base_server.post<MigrateResult>('/file/filesystem/migrate', data);
};
