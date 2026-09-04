// src/modules/rag/api/project.ts
// 知识库项目 API
import { http_base_server } from '@/common/api/http';
import type { PaginationParams, PaginationResponse } from '@/common/types/common';
import type { Project, ProjectCreate, ProjectUpdate } from '../types';

/**
 * 创建知识库项目(创建者自动成为项目管理员)
 * @param data 项目数据
 * @returns 项目ID
 */
export const createRagProject = (data: ProjectCreate) => {
  return http_base_server.post<string>('/rag/projects', data);
};

/** 项目列表过滤参数(type 别名具有隐式索引签名, 可直接传给 http 层) */
export type ProjectListParams = PaginationParams & {
  /** 项目名称模糊搜索 */
  name?: string;
  /** 知识库分类过滤(personal/project/company) */
  kb_category?: string;
  /** 私有状态过滤(true=私有/false=公开) */
  is_private?: boolean;
}

/**
 * 分页查询项目列表(支持名称/分类/私有状态多字段过滤)
 * @param params 分页与过滤参数
 */
export const listRagProjects = (params: ProjectListParams) => {
  return http_base_server.get<PaginationResponse<Project>>('/rag/projects/list', { params });
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
