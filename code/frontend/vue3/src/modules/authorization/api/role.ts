// src/modules/authorization/api/role.ts
import { http_base_server } from '@/common/api/http';
import type { PaginationParams, PaginationResponse } from '@/common/types/common';
import type { Role, RoleCreate, RoleUpdate } from '../types/role';

/** 创建角色 */
export const createRole = (role: RoleCreate) => {
  return http_base_server.post<string>('/authorization/roles', role);
};

/** 更新角色 */
export const updateRole = (roleId: string, role: RoleUpdate) => {
  return http_base_server.put<void>(`/authorization/roles/${roleId}`, role);
};

/** 删除角色 */
export const deleteRole = (roleId: string) => {
  return http_base_server.delete<void>(`/authorization/roles/${roleId}`);
};

/** 获取单个角色详情 */
export const getRole = (roleId: string) => {
  return http_base_server.get<Role>(`/authorization/roles/${roleId}`);
};

/** 分页查询角色列表 */
export const listRoles = (params: PaginationParams) => {
  return http_base_server.get<PaginationResponse<Role>>('/authorization/roles/list', { params });
};

/** 获取所有角色(不分页, 用于下拉选择) */
export const listAllRoles = () => {
  return http_base_server.get<Role[]>('/authorization/roles/all');
};

/** 通过名称获取角色 */
export const getRoleByName = (name: string) => {
  return http_base_server.get<Role>(`/authorization/roles/name/${name}`);
};

/** 通过权限字符串获取角色 */
export const getRoleByKey = (roleKey: string) => {
  return http_base_server.get<Role>(`/authorization/roles/key/${roleKey}`);
};
