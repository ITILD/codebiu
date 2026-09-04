// src/api/authorization/user.ts
import { http_base_server } from '@/utils/http';
import type { PaginationParams, PaginationResponse } from '@/types/common';
import type { User, UserCreate, UserUpdate } from '@/types/authorization/user';

/**
 * 创建新用户
 * @param user 用户数据
 * @returns 创建的用户ID
 */
export const createUser = (user: UserCreate) => {
  return http_base_server.post<object>('/authorization/users', user);
};

/**
 * 删除用户
 * @param userId 用户ID
 */
export const deleteUser = (userId: string) => {
  return http_base_server.delete<void>(`/authorization/users/${userId}`);
};

/**
 * 更新用户
 * @param userId 用户ID
 * @param user 用户数据
 */
export const updateUser = (userId: string, user: UserUpdate) => {
  return http_base_server.put<void>(`/authorization/users/${userId}`, user);
};

/**
 * 获取单个用户详情
 * @param userId 用户ID
 * @returns 用户详情
 */
export const getUser = (userId: string) => {
  return http_base_server.get<User>(`/authorization/users/${userId}`);
};

/**
 * 分页查询用户列表
 * @param params 分页参数
 * @returns 分页响应结果
 */
export const listUsers = (params: PaginationParams) => {
  return http_base_server.get<PaginationResponse<User>>('/authorization/users/list', { params });
};

/**
 * 用户认证
 * @param username 用户名
 * @param password 密码
 * @returns 认证成功的用户信息
 */
export const authenticateUser = (username: string, password: string) => {
  return http_base_server.post<User>('/authorization/users/authenticate', {
    username,
    password
  });
};