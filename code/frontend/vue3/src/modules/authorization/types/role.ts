// src/modules/authorization/types/role.ts

interface RoleBase {
  name: string;
  role_key: string;
  description?: string;
  sort: number;
  data_scope: string;
  is_active: boolean;
}

interface Role extends RoleBase {
  id: string;
  created_at: string;
  updated_at: string;
}

interface RoleCreate extends RoleBase {}

interface RoleUpdate {
  name?: string;
  role_key?: string;
  description?: string;
  sort?: number;
  data_scope?: string;
  is_active?: boolean;
}

const dataScopeOptions = [
  { label: '全部数据权限', value: '1' },
  { label: '自定数据权限', value: '2' },
  { label: '本部门数据权限', value: '3' },
  { label: '本部门及以下数据权限', value: '4' },
  { label: '仅本人数据权限', value: '5' },
];

export type { Role, RoleCreate, RoleUpdate, RoleBase };
export { dataScopeOptions };
