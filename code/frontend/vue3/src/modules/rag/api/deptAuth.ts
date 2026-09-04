// src/modules/rag/api/deptAuth.ts
// 知识库项目部门授权 API(部门批量授权,与个人成员档位取最高生效)
import { http_base_server } from '@/common/api/http';
import type { PaginationParams, PaginationResponse } from '@/common/types/common';
import type { DeptTree } from '@/modules/authorization/types/dept';
import type { ProjectDept, ProjectDeptCreate, ProjectDeptUpdate } from '../types';

/** 部门授权列表过滤参数 */
export type DeptAuthListParams = PaginationParams & {
  /** 授权档位过滤(project_admin/project_editor/project_reader) */
  role?: string;
}

/**
 * 添加部门授权(需要项目成员邀请权限)
 * @param data 授权数据(项目ID/部门ID/档位)
 * @returns 授权记录ID
 */
export const addProjectDept = (data: ProjectDeptCreate) => {
  return http_base_server.post<string>('/rag/project-depts', data);
};

/**
 * 获取部门树(仅需登录,供项目授权选择使用)
 * @returns 部门树列表
 */
export const getAuthDeptTree = () => {
  return http_base_server.get<DeptTree[]>('/rag/project-depts/dept-tree');
};

/**
 * 获取项目部门授权列表(支持档位过滤)
 * @param projectId 项目ID
 * @param params 分页与过滤参数
 */
export const listProjectDepts = (projectId: string, params: DeptAuthListParams) => {
  return http_base_server.get<PaginationResponse<ProjectDept>>(
    `/rag/project-depts/project/${projectId}`,
    { params }
  );
};

/**
 * 更新部门授权档位
 * @param id 授权记录ID
 * @param data 更新数据
 * @returns 更新后的授权记录
 */
export const updateProjectDept = (id: string, data: ProjectDeptUpdate) => {
  return http_base_server.put<ProjectDept>(`/rag/project-depts/${id}`, data);
};

/**
 * 移除部门授权
 * @param id 授权记录ID
 */
export const removeProjectDept = (id: string) => {
  return http_base_server.delete<void>(`/rag/project-depts/${id}`);
};
