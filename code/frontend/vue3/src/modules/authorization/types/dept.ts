// src/types/authorization/dept.ts

interface DeptBase {
  parent_id: string;
  ancestors?: string;
  name: string;
  order_num: number;
  leader?: string;
  phone?: string;
  email?: string;
  is_active: boolean;
}

interface Dept extends DeptBase {
  id: string;
  created_at: string;
  updated_at: string;
}

interface DeptCreate extends DeptBase {}

interface DeptUpdate {
  parent_id?: string;
  ancestors?: string;
  name?: string;
  order_num?: number;
  leader?: string;
  phone?: string;
  email?: string;
  is_active?: boolean;
}

interface DeptTree {
  id: string;
  parent_id: string;
  name: string;
  order_num: number;
  leader?: string;
  phone?: string;
  email?: string;
  is_active: boolean;
  children: DeptTree[];
}

export type { Dept, DeptCreate, DeptUpdate, DeptTree, DeptBase };
