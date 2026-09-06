// src/modules/rag/api/document.ts
// 知识库项目文档 API
// 上传链路复用公共统一存储流程(common/utils/storageUpload, 与文件管理同一套 S3 直传/中转),
// project_document 作为知识库独立口径记录; 上传成功后后端自动派发解析任务(模型缺失时返回告警)
import { http_base_server } from '@/common/api/http';
import { createStorageUploader } from '@/common/utils/storageUpload';
import type { MultipartPart } from '@/common/utils/storageUpload';
import type { PaginationParams, PaginationResponse } from '@/common/types/common';
import type { ProjectDocument, ProjectDocumentUpdate, SupportedFileTypes, DocumentIngestProgress } from '../types';

/** 上传模式缓存(direct=预签名直传 / proxy=服务端中转) */
interface RagUploadMode {
  mode: 'direct' | 'proxy';
  part_size: number;
  max_size: number;
}
let uploadModeCache: RagUploadMode | null = null;

/**
 * 查询知识库文档上传模式(首次调用获取并缓存,决定直传/中转策略)
 */
export const getRagUploadMode = async (): Promise<RagUploadMode> => {
  if (!uploadModeCache) {
    uploadModeCache = await http_base_server.get<RagUploadMode>(
      '/rag/project-documents/upload-mode'
    );
  }
  return uploadModeCache;
};

/** 模型预检结果(解析文档前校验 LLM/向量化模型是否可用) */
export interface ParseModelCheck {
  /** true 表示所需模型齐备 */
  ok: boolean;
  /** 缺失模型中文名列表(对话(LLM)/向量化(Embedding)) */
  missing: string[];
  /** 为空表示可用, 否则为弹窗警告文案 */
  message: string | null;
}

/**
 * 校验当前用户解析文档所需模型(对话+向量化)是否可用
 * 供前端在提交解析任务前弹窗警告
 */
export const checkRagParseModels = () => {
  return http_base_server.get<ParseModelCheck>(
    '/rag/project-documents/model-check'
  );
};

/**
 * 上传文档到指定项目(统一存储上传流程: 小文件直传/大文件分片/秒传自动分流)
 * @param projectId 项目ID
 * @param file 文件对象
 * @param description 文档描述
 * @param pid 父目录ID(为空上传到项目根文件夹)
 */
export const uploadRagDocument = (
  projectId: string,
  file: File,
  description?: string,
  pid?: string
) => {
  return ragDocumentUploader(file, { projectId, description, pid });
};

/** 分片上传初始化(凭证签发阶段完成秒传判断/内容登记) */
const initRagMultipart = (
  projectId: string,
  data: {
    filename: string;
    file_size_bytes: number;
    content_hash: string;
    content_type?: string;
    pid?: string;
  }
) => {
  return http_base_server.post<RagMultipartInitResponse>(
    `/rag/project-documents/${projectId}/multipart/init`,
    data
  );
};

/** proxy 模式分片中转(分片二进制经服务端保存;返回分片信息) */
const uploadRagMultipartPart = (
  projectId: string,
  uploadId: string,
  partNumber: number,
  content: ArrayBuffer
) => {
  return http_base_server.putRaw<MultipartPart>(
    `/rag/project-documents/${projectId}/multipart/${encodeURIComponent(uploadId)}/parts/${partNumber}`,
    content,
    { headers: { 'Content-Type': 'application/octet-stream' } }
  );
};

/** 完成分片上传(服务端对账合并并按知识库口径登记) */
const completeRagMultipart = (
  projectId: string,
  uploadId: string,
  data: {
    filename: string;
    description?: string;
    file_size_bytes: number;
    parts: MultipartPart[];
    pid?: string;
  }
) => {
  return http_base_server.post<ProjectDocument>(
    `/rag/project-documents/${projectId}/multipart/${encodeURIComponent(uploadId)}/complete`,
    data
  );
};

/** 秒传登记(内容已存在时直接创建知识库文档记录) */
const instantRegisterRagDocument = (
  projectId: string,
  data: {
    name: string;
    content_hash: string;
    file_size_bytes: number;
    mime_type?: string;
    description?: string;
    pid?: string;
  }
) => {
  return http_base_server.post<ProjectDocument>(
    `/rag/project-documents/${projectId}/upload-complete`,
    data
  );
};

/** 分片上传初始化响应(mode=direct 时 part_urls 与分片号一一对应) */
interface RagMultipartInitResponse {
  is_existing: boolean;
  upload_id: string | null;
  part_size: number;
  mode: 'direct' | 'proxy';
  part_urls: string[] | null;
}

/** 知识库文档统一存储上传器(端点适配器: 记录口径为 project_document) */
const ragDocumentUploader = createStorageUploader<
  { projectId: string; description?: string; pid?: string },
  ProjectDocument
>({
  getMode: getRagUploadMode,
  init: (file, contentHash, ctx) =>
    initRagMultipart(ctx!.projectId, {
      filename: file.name,
      file_size_bytes: file.size,
      content_hash: contentHash,
      content_type: file.type || undefined,
      pid: ctx?.pid,
    }),
  uploadPart: (uploadId, partNumber, content, ctx) =>
    uploadRagMultipartPart(ctx!.projectId, uploadId, partNumber, content),
  complete: (file, uploadId, parts, ctx) =>
    completeRagMultipart(ctx!.projectId, uploadId, {
      filename: file.name,
      description: ctx?.description,
      file_size_bytes: file.size,
      parts,
      pid: ctx?.pid,
    }),
  instant: (file, contentHash, ctx) =>
    instantRegisterRagDocument(ctx!.projectId, {
      name: file.name,
      content_hash: contentHash,
      file_size_bytes: file.size,
      mime_type: file.type || undefined,
      description: ctx?.description,
      pid: ctx?.pid,
    }),
});

/** 文档列表过滤参数(type 别名具有隐式索引签名, 可直接传给 http 层) */
export type DocumentListParams = PaginationParams & {
  /** 文档名称模糊搜索 */
  name?: string;
  /** 解析状态过滤(pending/parsing/completed/failed) */
  parse_status?: string;
}

/**
 * 分页查询项目文档列表(支持名称/解析状态多字段过滤)
 * @param projectId 项目ID
 * @param params 分页与过滤参数
 */
export const listRagProjectDocuments = (
  projectId: string,
  params: DocumentListParams
) => {
  return http_base_server.get<PaginationResponse<ProjectDocument>>(
    `/rag/project-documents/${projectId}/list`,
    { params }
  );
};

/**
 * 获取文档详情
 * @param documentId 文档ID
 */
export const getRagDocument = (documentId: string) => {
  return http_base_server.get<ProjectDocument>(
    `/rag/project-documents/${documentId}`
  );
};

/**
 * 获取文档入库步骤与进度(解析→拆分chunk→向量化, 含预留步骤占位)
 * @param documentId 文档ID
 */
export const getRagDocumentIngestProgress = (documentId: string) => {
  return http_base_server.get<DocumentIngestProgress>(
    `/rag/project-documents/${documentId}/progress`
  );
};

/**
 * 获取文档下载地址(相对后端路径)
 * @param documentId 文档ID
 */
export const getRagDocumentDownloadUrl = (documentId: string) => {
  return `/base_server/rag/project-documents/${documentId}/download`;
};

/**
 * 更新文档信息(名称/描述)
 * @param documentId 文档ID
 * @param data 更新数据
 */
export const updateRagDocument = (
  documentId: string,
  data: ProjectDocumentUpdate
) => {
  return http_base_server.put<void>(
    `/rag/project-documents/${documentId}`,
    data
  );
};

/**
 * 删除文档(同时删除物理文件与数据库记录)
 * @param documentId 文档ID
 */
export const deleteRagDocument = (documentId: string) => {
  return http_base_server.delete<void>(`/rag/project-documents/${documentId}`);
};

/**
 * 重新解析文档(同步)
 * @param documentId 文档ID
 */
export const reparseRagDocument = (documentId: string) => {
  return http_base_server.post<boolean>(
    `/rag/project-documents/${documentId}/reparse`
  );
};

/**
 * 重新解析文档(异步任务队列)
 * @param documentId 文档ID
 */
export const reparseRagDocumentTask = (documentId: string) => {
  return http_base_server.post<{ message: string; document_id: string }>(
    `/rag/project-documents/${documentId}/reparse-task`
  );
};

/**
 * 获取支持上传的文件格式列表
 */
export const getSupportedFileTypes = () => {
  return http_base_server.get<{
    code: number;
    message: string;
    data: SupportedFileTypes;
  }>('/rag/project-documents/supported-types');
};

// ===== 知识库文件夹与条目浏览(虚拟目录条目级) =====

/** 项目内文件条目(虚拟目录条目, 与文件管理共用 FileEntry 结构) */
export interface RagFileEntry {
  id: string;
  /** 父目录ID(顶层为 null) */
  pid: string | null;
  name: string;
  /** 完整逻辑路径(如 /知识库/项目A/手册) */
  logical_path: string;
  is_directory: boolean;
  file_size_bytes: number | null;
  file_extension: string | null;
  mime_type: string | null;
  /** 来源模块标记(rag=知识库业务条目) */
  source_module: string | null;
  description: string | null;
  created_at: string;
  updated_at: string;
  /** ===== 文档级联查字段(仅文件条目, 后端 list_entries 联查 project_document 补充) ===== */
  /** 关联文档ID(为空表示旧数据未登记文档记录) */
  document_id?: string | null;
  /** 解析状态(pending/parsing/completed/failed) */
  parse_status?: string | null;
  /** 解析生成的分块数量 */
  chunk_count?: number | null;
  /** 解析失败原因 */
  error_message?: string | null;
}

/** 项目条目浏览过滤参数 */
export type RagEntryListParams = PaginationParams & {
  /** 父目录ID(为空浏览项目根文件夹) */
  pid?: string;
  /** 名称模糊过滤 */
  name?: string;
};

/**
 * 分页浏览项目内文件夹与文件(目录排前,名称排序)
 * @param projectId 项目ID
 * @param params 分页与过滤参数
 */
export const listRagEntries = (
  projectId: string,
  params: RagEntryListParams
) => {
  return http_base_server.get<PaginationResponse<RagFileEntry>>(
    `/rag/project-documents/${projectId}/entries`,
    { params }
  );
};

/**
 * 在项目内创建文件夹
 * @param projectId 项目ID
 * @param name 文件夹名称
 * @param pid 父目录ID(为空创建到项目根文件夹)
 */
export const createRagFolder = (projectId: string, name: string, pid?: string) => {
  const query = new URLSearchParams({ name });
  if (pid) query.set('pid', pid);
  return http_base_server.post<RagFileEntry>(
    `/rag/project-documents/${projectId}/folders?${query.toString()}`
  );
};

/**
 * 重命名项目内文件夹
 * @param projectId 项目ID
 * @param folderId 文件夹条目ID
 * @param name 新名称
 */
export const renameRagFolder = (
  projectId: string,
  folderId: string,
  name: string
) => {
  return http_base_server.put<RagFileEntry>(
    `/rag/project-documents/${projectId}/folders/${folderId}?name=${encodeURIComponent(name)}`
  );
};

/**
 * 删除项目内文件夹(递归删除条目并释放内容引用)
 * @param projectId 项目ID
 * @param folderId 文件夹条目ID
 */
export const deleteRagFolder = (projectId: string, folderId: string) => {
  return http_base_server.delete<void>(
    `/rag/project-documents/${projectId}/folders/${folderId}`
  );
};
