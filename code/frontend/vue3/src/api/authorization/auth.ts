// src/api/authorization/auth.ts
import { http_base_server } from '@/utils/http';
import type {
  AuthLoginRequest,
  AuthLogoutRequest,
  AuthRegisterRequest,
  AuthResponse,
  RefreshTokenRequest
} from '@/types/authorization/auth';

/**
 * 用户注册
 * @param user 用户注册数据
 * @returns 认证响应，包含令牌和用户信息
 */
export const registerUser = (user: AuthRegisterRequest) => {
  return http_base_server.post<AuthResponse>('/authorization/auth/register', user);
};

/**
 * 用户登录
 * @param credentials 登录凭证
 * @returns 认证响应，包含令牌和用户信息
 */
export const loginUser = (credentials: AuthLoginRequest) => {
  // 注意：OAuth2PasswordRequestForm 需要使用 FormData
  const formData = new FormData();
  formData.append('username', credentials.username);
  formData.append('password', credentials.password);
  
  return http_base_server.post<AuthResponse>('/authorization/auth/login', formData);
};

/**
 * 用户登出
 * @param logoutRequest 登出请求数据
 * @returns 是否成功登出
 */
export const logoutUser = (logoutRequest: AuthLogoutRequest) => {
  return http_base_server.post<boolean>('/authorization/auth/logout', logoutRequest);
};

/**
 * 刷新访问令牌
 * @param refreshRequest 刷新令牌请求数据
 * @returns 新的访问令牌
 */
export const refreshToken = (refreshRequest: RefreshTokenRequest) => {
  return http_base_server.post<AuthResponse['tokens']['access']>('/authorization/auth/refresh', refreshRequest);
};

/**
 * 获取当前用户信息
 * @returns 当前用户信息
 */
export const getCurrentUser = () => {
  return http_base_server.get<AuthResponse['user']>('/authorization/auth/me');
};

/**
 * 获取当前用户ID
 * @returns 当前用户ID
 */
export const getCurrentUserId = () => {
  return http_base_server.get<string>('/authorization/auth/me_id');
};