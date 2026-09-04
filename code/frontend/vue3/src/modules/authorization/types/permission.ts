// src/modules/authorization/types/permission.ts

interface PermissionBase {
  parent_id: string;
  name: string;
  code: string;
  description?: string;
  menu_type: string;
  path?: string;
  component?: string;
  perms?: string;
  icon?: string;
  order_num: number;
  visible: boolean;
  is_active: boolean;
}

interface Permission extends PermissionBase {
  id: string;
  created_at: string;
  updated_at: string;
}

interface PermissionCreate extends PermissionBase {}

interface PermissionUpdate {
  parent_id?: string;
  name?: string;
  code?: string;
  description?: string;
  menu_type?: string;
  path?: string;
  component?: string;
  perms?: string;
  icon?: string;
  order_num?: number;
  visible?: boolean;
  is_active?: boolean;
}

interface PermissionTree {
  id: string;
  parent_id: string;
  name: string;
  code: string;
  menu_type: string;
  perms?: string;
  icon?: string;
  order_num: number;
  visible: boolean;
  is_active: boolean;
  children: PermissionTree[];
}

const menuTypeOptions = [
  { label: '目录', value: 'M' },
  { label: '菜单', value: 'C' },
  { label: '按钮', value: 'F' },
];

export type { Permission, PermissionCreate, PermissionUpdate, PermissionTree, PermissionBase };
export { menuTypeOptions };
