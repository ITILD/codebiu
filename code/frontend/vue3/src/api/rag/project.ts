// src/api/rag/project.ts
// 知识库项目 API
import { http_base_server } from '@/utils/http';
import type { PaginationParams, PaginationResponse } from '@/types/common';
import type { Project, ProjectCreate, ProjectUpdate } from '@/types/rag';

/**
 * 创建知识库项目(创建者自动成为项目管理员)
 * @param data 项目数据
 * @returns 项目ID
 */
export const createRagProject = (data: ProjectCreate) => {
  return http_base_server.post<string>('/rag/projects', data);
};

/**
 * 分页查询项目列表
 * @param params 分页参数
 * @param kbCategory 知识库分类过滤(personal/project/company)
 */
export const listRagProjects = (params: PaginationParams, kbCategory?: string) => {
  return http_base_server.get<PaginationResponse<Project>>('/rag/projects/list', {
    params: kbCategory ? { ...params, kb_category: kbCategory } : params,
  });
};

/**
 * 获取项目详情
 * @param projectId 项目ID
 */
export const getRagProject = (projectId: string) => {
  return http_base_server.get<Project>(`/rag/projects/${projectId}`);
};

/**
 * 更新项目
 * @param projectId 项目ID
 * @param data 更新数据
 */
export const updateRagProject = (projectId: string, data: ProjectUpdate) => {
  return http_base_server.put<void>(`/rag/projects/${projectId}`, data);
};

/**
 * 删除项目(级联清理文档/成员/向量)
 * @param projectId 项目ID
 */
export const deleteRagProject = (projectId: string) => {
  return http_base_server.delete<void>(`/rag/projects/${projectId}`);
};
