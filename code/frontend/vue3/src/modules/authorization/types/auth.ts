// src/modules/authorization/types/auth.ts
import type { User } from './user';
import type { TokenResponseBase } from './token';

export interface AuthResponse {
  tokens: {
    access: TokenResponseBase;
    refresh: TokenResponseBase;
  };
  user: User;
  message: string;
}

export interface AuthLoginRequest {
  username: string;
  password: string;
}

export interface AuthRegisterRequest {
  username: string;
  password: string;
  email?: string;
  phone?: string;
  nickname?: string;
  /** 邮箱验证码(后端开启 email.use_for_register 时必填) */
  code?: string;
}

/** 注册流程配置(后端 email.use_for_register 开关) */
export interface RegisterConfig {
  /** 注册是否需要邮箱验证码 */
  email_verify: boolean;
}

export interface AuthLogoutRequest {
  token_access: string;
  token_refresh: string;
  token_refresh_id: string;
}

export interface RefreshTokenRequest {
  token_refresh: string;
}

/** 当前用户角色与权限码信息(me-permissions 接口响应) */
export interface UserPermissionInfo {
  /** 角色绑定,按域分组,如 { "*": ["admin"], "main": ["main_viewer"] } */
  roles: Record<string, string[]>;
  /** 权限码列表,全局管理员为 ["*"] */
  permissions: string[];
}