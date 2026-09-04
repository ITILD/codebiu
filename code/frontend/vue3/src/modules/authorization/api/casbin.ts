// src/modules/authorization/api/casbin.ts
import { http_base_server } from '@/common/api/http';

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
  return http_base_server.post('/authorization/casbin-rules/role-user', data);
};

/** 删除用户的角色 */
export const removeRoleForUser = (data: RoleForUserRequest) => {
  return http_base_server.delete('/authorization/casbin-rules/role-user', {
    body: JSON.stringify(data),
  });
};

/** 获取用户的所有角色 */
export const getRolesForUser = (userId: string, dom = '*') => {
  return http_base_server.get<{ message: string; data: string[] }>(
    `/authorization/casbin-rules/roles/${userId}`,
    { params: { dom } }
  );
};

/** 获取角色的所有权限 */
export const getPermissionsForRole = (roleKey: string, dom = '*') => {
  return http_base_server.get<{ message: string; data: { domain: string; permission_code: string; method: string }[] }>(
    `/authorization/casbin-rules/permissions/${roleKey}`,
    { params: { dom } }
  );
};

/** 检查用户是否有指定权限 */
export const checkPermission = (data: CheckPermissionRequest) => {
  return http_base_server.post<{ has_permission: boolean }>('/authorization/casbin-rules/check-permission', data);
};

/** 批量添加角色权限 */
export const batchAddRolePermissions = (data: BatchAddRolePermissionsRequest) => {
  return http_base_server.post('/authorization/casbin-rules/batch-role-permissions', data);
};

/** 批量添加用户角色 */
export const batchAddUserRoles = (data: BatchAddUserRolesRequest) => {
  return http_base_server.post('/authorization/casbin-rules/batch-user-roles', data);
};

/** 删除角色的所有权限 */
export const deleteRolePermissions = (roleKey: string, dom = '*') => {
  return http_base_server.delete(`/authorization/casbin-rules/role-permissions/${roleKey}`, {
    params: { dom },
  });
};

/** 删除用户的所有角色 */
export const deleteUserRoles = (userId: string, dom = '*') => {
  return http_base_server.delete(`/authorization/casbin-rules/user-roles/${userId}`, {
    params: { dom },
  });
};

/** 重新加载策略 */
export const reloadPolicy = () => {
  return http_base_server.post('/authorization/casbin-rules/reload-policy');
};

/** 策略规则(主体, 域, 资源, 动作) */
interface PolicyRow {
  sub: string;
  dom: string;
  obj: string;
  act: string;
}

/** 用户-角色绑定规则(用户ID, 角色键, 域) */
interface GroupingPolicyRow {
  user_id: string;
  role_key: string;
  dom: string;
}

/** 获取全部策略规则(可按域过滤) */
export const getAllPolicies = (dom?: string) => {
  return http_base_server.get<{ message: string; data: PolicyRow[] }>(
    '/authorization/casbin-rules/policies',
    { params: dom ? { dom } : {} }
  );
};

/** 获取全部用户-角色绑定规则(可按域过滤) */
export const getAllGroupingPolicies = (dom?: string) => {
  return http_base_server.get<{ message: string; data: GroupingPolicyRow[] }>(
    '/authorization/casbin-rules/grouping-policies',
    { params: dom ? { dom } : {} }
  );
};

/** 添加策略规则 */
export const addPolicy = (data: PolicyRequest) => {
  return http_base_server.post('/authorization/casbin-rules/policy', data);
};

/** 删除策略规则 */
export const removePolicy = (data: PolicyRequest) => {
  return http_base_server.delete('/authorization/casbin-rules/policy', {
    body: JSON.stringify(data),
  });
};

// ---------------- 模块声明树与角色授权(声明驱动) ----------------

/** 模块权限声明树节点(目录/菜单/按钮) */
interface ModulePermNode {
  name: string;
  code: string;
  menu_type: string;
  path?: string | null;
  icon?: string | null;
  order_num: number;
  children: ModulePermNode[];
}

/**
 * 获取全部模块声明的权限树(角色授权界面的可分配权限集合)
 * @returns 模块权限声明树
 */
export const getModuleTree = () => {
  return http_base_server.get<{ message: string; data: ModulePermNode[] }>(
    '/authorization/casbin-rules/module-tree'
  );
};

/**
 * 获取角色当前拥有的节点级权限码列表(角色授权界面勾选回显)
 * @param roleKey 角色键
 * @returns 按钮级权限码列表
 */
export const getRolePermCodes = (roleKey: string) => {
  return http_base_server.get<{ message: string; data: string[] }>(
    `/authorization/casbin-rules/role-perms/${roleKey}`
  );
};

/**
 * 全量同步角色的节点级权限(提交勾选的权限码,按钮级权限码自动解析为casbin策略)
 * @param roleKey 角色键
 * @param codes 勾选的权限码列表
 */
export const syncRolePermissions = (roleKey: string, codes: string[]) => {
  return http_base_server.post<{ message: string; data: { removed: number; added: number } }>(
    '/authorization/casbin-rules/role-perms',
    { role_key: roleKey, codes }
  );
};

export type {
  PolicyRequest,
  RoleForUserRequest,
  BatchAddRolePermissionsRequest,
  BatchAddUserRolesRequest,
  CheckPermissionRequest,
  PolicyRow,
  GroupingPolicyRow,
  ModulePermNode,
};
