// src/modules/authorization/api/auth.ts
import { http_base_server } from '@/common/api/http';
import type {
  AuthLoginRequest,
  AuthLogoutRequest,
  AuthRegisterRequest,
  AuthResponse,
  RefreshTokenRequest,
  UserPermissionInfo
} from '../types/auth';

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
  return http_base_server.get<string>('/authorization/auth/me-id');
};

/**
 * 获取当前用户的角色与权限码(菜单过滤/按钮权限判断依据)
 * @returns 角色按域分组 + 权限码列表(全局管理员为 ["*"])
 */
export const getUserPermissions = () => {
  return http_base_server.get<UserPermissionInfo>('/authorization/auth/me-permissions');
};

/** 自助资料更新请求(仅展示类字段) */
export interface SelfProfileUpdate {
  nickname?: string;
  email?: string;
  phone?: string;
  avatar?: string;
}

/** 修改密码请求(需验证旧密码) */
export interface PasswordChangeRequest {
  old_password: string;
  new_password: string;
}

/**
 * 自助更新个人资料(昵称/邮箱/电话/头像,登录即可修改自己)
 * @returns 更新后的用户信息
 */
export const updateMyProfile = (data: SelfProfileUpdate) => {
  return http_base_server.put<AuthResponse['user']>('/authorization/auth/me', data);
};

/**
 * 自助修改密码(需验证旧密码,成功返回204)
 */
export const changeMyPassword = (data: PasswordChangeRequest) => {
  return http_base_server.put<null>('/authorization/auth/me/password', data);
};

/** 头像上传响应 */
export interface AvatarUploadResponse {
  /** 头像下载路径(/base_server/file/filesystem/download/{entry_id}, <img> 直接可用) */
  avatar: string;
  /** 虚拟目录文件条目ID */
  entry_id: string;
}

/**
 * 上传当前用户头像(登录即可;后端经统一文件服务存入 /用户头像/<用户ID>/ 并清理旧头像)
 * @param file 图片文件(png/jpg/jpeg/gif/webp/svg/bmp)
 */
export const uploadMyAvatar = (file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  return http_base_server.post<AvatarUploadResponse>(
    '/authorization/auth/me/avatar',
    formData
  );
};

/**
 * 删除当前用户头像(登录即可;后端清理头像文件条目并置空头像字段,
 * 前端回退为用户名首字默认头像)
 */
export const deleteMyAvatar = () => {
  return http_base_server.delete<null>('/authorization/auth/me/avatar');
};
