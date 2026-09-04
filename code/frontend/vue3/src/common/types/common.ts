// src/common/types/common.ts
export enum ScrollDirection {
  UP = "up",
  DOWN = "down"
}

// 注意: 使用 type 而非 interface，type 别名具有隐式索引签名，
// 可直接赋值给 http 层的 Record<string, QueryParamValue> 查询参数类型
export type PaginationParams = {
  page: number;
  size: number;
  sort?: string;
}

export type PaginationResponse<T> = {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export type InfiniteScrollParams = {
  last_id?: string;
  limit: number;
  direction?: ScrollDirection;
  sort_by?: string;
}

export type InfiniteScrollResponse<T> = {
  items: T[];
  last_id?: string;
  has_more: boolean;
}