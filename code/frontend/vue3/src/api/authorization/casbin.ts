// src/api/authorization/casbin.ts
import { http_base_server } from '@/utils/http';

interface PolicyRequest {
  sub: string;
  dom: string;
  obj: string;
  act: string;
}

interface RoleForUserRequest {
  user_id: string;
  role_key: string;
  dom?: string;
}

interface BatchAddRolePermissionsRequest {
  role_key: string;
  dom?: string;
  permissions: { permission_code: string; method: string }[];
}

interface BatchAddUserRolesRequest {
  user_id: string;
  role_keys: string[];
  dom?: string;
}

interface CheckPermissionRequest {
  user_id: string;
  dom: string;
  obj: string;
  act: string;
}

/** 为用户添加角色 */
export const addRoleForUser = (data: RoleForUserRequest) => {
  return http_base_server.post('/authorization/casbin_rules/role-user', data);
};

/** 删除用户的角色 */
export const removeRoleForUser = (data: RoleForUserRequest) => {
  return http_base_server.delete('/authorization/casbin_rules/role-user', {
    body: JSON.stringify(data),
  });
};

/** 获取用户的所有角色 */
export const getRolesForUser = (userId: string, dom = '*') => {
  return http_base_server.get<{ message: string; data: string[] }>(
    `/authorization/casbin_rules/roles/${userId}`,
    { params: { dom } }
  );
};

/** 获取角色的所有权限 */
export const getPermissionsForRole = (roleKey: string, dom = '*') => {
  return http_base_server.get<{ message: string; data: { domain: string; permission_code: string; method: string }[] }>(
    `/authorization/casbin_rules/permissions/${roleKey}`,
    { params: { dom } }
  );
};

/** 检查用户是否有指定权限 */
export const checkPermission = (data: CheckPermissionRequest) => {
  return http_base_server.post<{ has_permission: boolean }>('/authorization/casbin_rules/check-permission', data);
};

/** 批量添加角色权限 */
export const batchAddRolePermissions = (data: BatchAddRolePermissionsRequest) => {
  return http_base_server.post('/authorization/casbin_rules/batch-role-permissions', data);
};

/** 批量添加用户角色 */
export const batchAddUserRoles = (data: BatchAddUserRolesRequest) => {
  return http_base_server.post('/authorization/casbin_rules/batch-user-roles', data);
};

/** 删除角色的所有权限 */
export const deleteRolePermissions = (roleKey: string, dom = '*') => {
  return http_base_server.delete(`/authorization/casbin_rules/role-permissions/${roleKey}`, {
    params: { dom },
  });
};

/** 删除用户的所有角色 */
export const deleteUserRoles = (userId: string, dom = '*') => {
  return http_base_server.delete(`/authorization/casbin_rules/user-roles/${userId}`, {
    params: { dom },
  });
};

/** 重新加载策略 */
export const reloadPolicy = () => {
  return http_base_server.post('/authorization/casbin_rules/reload-policy');
};

export type { PolicyRequest, RoleForUserRequest, BatchAddRolePermissionsRequest, BatchAddUserRolesRequest, CheckPermissionRequest };
