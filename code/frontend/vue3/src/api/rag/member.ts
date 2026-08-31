// src/api/rag/member.ts
// 知识库项目成员 API(同知识库多用户配置)
import { http_base_server } from '@/utils/http';
import type { PaginationParams, PaginationResponse } from '@/types/common';
import type { ProjectMember, ProjectMemberCreate, ProjectMemberUpdate, MyProject } from '@/types/rag';

/**
 * 添加项目成员(同步授予 casbin 项目域角色)
 * @param data 成员数据
 * @returns 成员ID
 */
export const addProjectMember = (data: ProjectMemberCreate) => {
  return http_base_server.post<string>('/rag/project-members', data);
};

/**
 * 获取我参与的项目及我的角色
 * @param params 分页参数
 */
export const listMyProjects = (params: PaginationParams) => {
  return http_base_server.get<PaginationResponse<MyProject>>(
    '/rag/project-members/my',
    { params }
  );
};

/** 成员列表过滤参数(type 别名具有隐式索引签名, 可直接传给 http 层) */
export type MemberListParams = PaginationParams & {
  /** 项目角色过滤(project_admin/project_editor/project_reader) */
  role?: string;
  /** 用户名/昵称模糊搜索 */
  user_keyword?: string;
}

/**
 * 获取项目成员列表(支持角色过滤)
 * @param projectId 项目ID
 * @param params 分页与过滤参数
 */
export const listProjectMembers = (
  projectId: string,
  params: MemberListParams
) => {
  return http_base_server.get<PaginationResponse<ProjectMember>>(
    `/rag/project-members/project/${projectId}`,
    { params }
  );
};

/**
 * 获取单个成员详情
 * @param memberId 成员ID
 */
export const getProjectMember = (memberId: string) => {
  return http_base_server.get<ProjectMember>(
    `/rag/project-members/${memberId}`
  );
};

/**
 * 移除项目成员(同步撤销 casbin 项目域角色)
 * @param memberId 成员ID
 */
export const removeProjectMember = (memberId: string) => {
  return http_base_server.delete<void>(`/rag/project-members/${memberId}`);
};

/**
 * 更新项目成员角色
 * @param memberId 成员ID
 * @param data 角色更新数据
 */
export const updateProjectMember = (
  memberId: string,
  data: ProjectMemberUpdate
) => {
  return http_base_server.put<void>(`/rag/project-members/${memberId}`, data);
};
