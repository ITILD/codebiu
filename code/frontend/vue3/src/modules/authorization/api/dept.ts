// src/modules/authorization/api/dept.ts
import { http_base_server } from '@/common/api/http';
import type { Dept, DeptCreate, DeptUpdate, DeptTree } from '../types/dept';

/** 获取部门树形结构 */
export const getDeptTree = () => {
  return http_base_server.get<DeptTree[]>('/authorization/depts/tree');
};

/** 获取部门列表(扁平) */
export const listDepts = () => {
  return http_base_server.get<Dept[]>('/authorization/depts/list');
};

/** 获取单个部门详情 */
export const getDept = (deptId: string) => {
  return http_base_server.get<Dept>(`/authorization/depts/${deptId}`);
};

/** 创建部门 */
export const createDept = (dept: DeptCreate) => {
  return http_base_server.post<Dept>('/authorization/depts', dept);
};

/** 更新部门 */
export const updateDept = (deptId: string, dept: DeptUpdate) => {
  return http_base_server.put<void>(`/authorization/depts/${deptId}`, dept);
};

/** 删除部门 */
export const deleteDept = (deptId: string) => {
  return http_base_server.delete<void>(`/authorization/depts/${deptId}`);
};
