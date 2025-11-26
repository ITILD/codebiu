// src/types/authorization/auth.ts
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
}

export interface AuthLogoutRequest {
  token_access: string;
  token_refresh: string;
  token_refresh_id: string;
}

export interface RefreshTokenRequest {
  token_refresh: string;
}