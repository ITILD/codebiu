//! 认证 DTO(对齐 Python do/auth.py: 登录/注册/登出/刷新的请求与响应)

use serde::{Deserialize, Serialize};

use crate::do_::user::UserResponse;

// ############################# 令牌响应 #############################

/// 单个令牌响应(token_id 仅刷新令牌有值)
#[derive(Debug, Clone, Serialize)]
pub struct TokenResponseBase {
    pub token: String,
    pub expires_in: i64,
    pub token_id: Option<String>,
}

/// 双令牌响应
#[derive(Debug, Clone, Serialize)]
pub struct TokenResponseFull {
    pub access: TokenResponseBase,
    pub refresh: TokenResponseBase,
}

/// 认证响应(message 字段默认 "register success", 与 Python 字段默认值行为一致)
#[derive(Debug, Clone, Serialize)]
pub struct AuthResponse {
    pub tokens: TokenResponseFull,
    pub user: UserResponse,
    pub message: String,
}

impl AuthResponse {
    pub fn new(tokens: TokenResponseFull, user: UserResponse) -> Self {
        Self { tokens, user, message: "register success".to_string() }
    }
}

// ############################# 认证请求 #############################

/// 登出请求
#[derive(Debug, Clone, Deserialize)]
pub struct AuthLogoutRequest {
    pub token_access: String,
    pub token_refresh: String,
    pub token_refresh_id: String,
}

/// 自助资料更新(仅展示类字段)
#[derive(Debug, Clone, Deserialize, Default)]
pub struct SelfProfileUpdate {
    #[serde(default)]
    pub nickname: Option<String>,
    #[serde(default)]
    pub email: Option<String>,
    #[serde(default)]
    pub phone: Option<String>,
    #[serde(default)]
    pub avatar: Option<String>,
}

/// 修改密码请求
#[derive(Debug, Clone, Deserialize)]
pub struct PasswordChange {
    pub old_password: String,
    pub new_password: String,
}

/// 注册请求
#[derive(Debug, Clone, Deserialize)]
pub struct RegisterRequest {
    pub username: String,
    pub password: String,
    #[serde(default)]
    pub email: Option<String>,
    #[serde(default)]
    pub phone: Option<String>,
    #[serde(default)]
    pub nickname: Option<String>,
    #[serde(default)]
    pub code: Option<String>,
}

/// 注册验证码发送请求
#[derive(Debug, Clone, Deserialize)]
pub struct RegisterCodeRequest {
    pub email: String,
}

/// 注册流程配置响应
#[derive(Debug, Clone, Serialize)]
pub struct RegisterConfigResponse {
    pub email_verify: bool,
}

/// 刷新令牌请求(auth 端点 /refresh)
#[derive(Debug, Clone, Deserialize)]
pub struct RefreshTokenRequest {
    pub token_refresh: String,
}
