// src/api/rag/document.ts
// 知识库项目文档 API
import { http_base_server } from '@/utils/http';
import type { PaginationParams, PaginationResponse } from '@/types/common';
import type { ProjectDocument, ProjectDocumentUpdate, SupportedFileTypes } from '@/types/rag';

/**
 * 上传文档到指定项目
 * @param projectId 项目ID
 * @param file 文件对象
 * @param description 文档描述
 */
export const uploadRagDocument = (
  projectId: string,
  file: File,
  description?: string
) => {
  const formData = new FormData();
  formData.append('file', file);
  if (description) formData.append('description', description);
  return http_base_server.post<ProjectDocument>(
    `/rag/project-documents/${projectId}/upload`,
    formData
  );
};

/**
 * 分页查询项目文档列表
 * @param projectId 项目ID
 * @param params 分页参数
 */
export const listRagProjectDocuments = (
  projectId: string,
  params: PaginationParams
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
    `/rag/project-documents/${documentId}/reparse_task`
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
