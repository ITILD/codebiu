// src/api/authorization/permission.ts
import { http_base_server } from '@/utils/http';
import type { PaginationParams, PaginationResponse } from '@/types/common';
import type { Permission, PermissionCreate, PermissionUpdate, PermissionTree } from '@/types/authorization/permission';

/** 创建权限/菜单 */
export const createPermission = (permission: PermissionCreate) => {
  return http_base_server.post<string>('/authorization/permissions', permission);
};

/** 更新权限/菜单 */
export const updatePermission = (permissionId: string, permission: PermissionUpdate) => {
  return http_base_server.put<void>(`/authorization/permissions/${permissionId}`, permission);
};

/** 删除权限/菜单 */
export const deletePermission = (permissionId: string) => {
  return http_base_server.delete<void>(`/authorization/permissions/${permissionId}`);
};

/** 获取单个权限详情 */
export const getPermission = (permissionId: string) => {
  return http_base_server.get<Permission>(`/authorization/permissions/${permissionId}`);
};

/** 分页查询权限列表 */
export const listPermissions = (params: PaginationParams) => {
  return http_base_server.get<PaginationResponse<Permission>>('/authorization/permissions/list', { params });
};

/** 获取权限树形结构 */
export const getPermissionTree = () => {
  return http_base_server.get<PermissionTree[]>('/authorization/permissions/tree');
};

/** 通过代码获取权限 */
export const getPermissionByCode = (code: string) => {
  return http_base_server.get<Permission>(`/authorization/permissions/code/${code}`);
};

/** 获取子权限列表 */
export const getPermissionsByParentId = (parentId: string) => {
  return http_base_server.get<Permission[]>(`/authorization/permissions/parent/${parentId}`);
};
