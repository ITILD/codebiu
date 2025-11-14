// src/types/common.ts
export enum ScrollDirection {
  UP = "up",
  DOWN = "down"
}

export interface PaginationParams {
  page: number;
  size: number;
  sort?: string;
}

export interface PaginationResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface InfiniteScrollParams {
  last_id?: string;
  limit: number;
  direction?: ScrollDirection;
  sort_by?: string;
}

export interface InfiniteScrollResponse<T> {
  items: T[];
  last_id?: string;
  has_more: boolean;
}