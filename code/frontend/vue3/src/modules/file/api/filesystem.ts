// src/api/file/filesystem.ts
// 文件模块 API(虚拟文件系统,后端存储可配置切换本地/rustfs)
import { http_base_server } from '@/utils/http';
import type { PaginationParams, PaginationResponse } from '@/types/common';
import type { FileEntry, FileEntryUpdate } from '@/types/file';

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
    '/file/filesystem/list_dir',
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
 * 上传文件到指定目录
 * @param file 文件对象
 * @param pid 父目录ID(为空上传到根目录)
 * @param description 文件描述
 */
export const uploadFile = (
  file: File,
  pid?: string,
  description?: string
) => {
  const formData = new FormData();
  formData.append('file', file);
  if (description) formData.append('description', description);
  return http_base_server.post<FileEntry>(
    '/file/filesystem/upload',
    formData,
    { params: { pid: pid || undefined } }
  );
};

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
  return http_base_server.get<FileEntry>(`/file/filesystem/file_entry/${entryId}`);
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
    `/file/filesystem/entry/${entryId}`,
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
    `/file/filesystem/entry/${entryId}/rename`,
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
    `/file/filesystem/entry/${entryId}/move`,
    null,
    { params: { target_pid: targetPid || undefined } }
  );
};

/**
 * 删除文件
 * @param entryId 文件ID
 */
export const deleteFile = (entryId: string) => {
  return http_base_server.delete<void>(`/file/filesystem/file/${entryId}`);
};

/**
 * 递归删除目录(含全部子项)
 * @param folderId 目录ID
 */
export const deleteFolder = (folderId: string) => {
  return http_base_server.delete<void>(`/file/filesystem/folder/${folderId}`);
};
