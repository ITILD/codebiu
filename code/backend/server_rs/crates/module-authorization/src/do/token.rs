//! 令牌管理 DTO(对齐 Python do/token.py: /authorization/tokens 端点请求体)

use serde::Deserialize;

/// 令牌创建请求(tokens 端点)
#[derive(Debug, Clone, Deserialize)]
pub struct TokenCreateRequest {
    pub user_id: String,
    /// "access"(默认) / "refresh"
    #[serde(default)]
    pub token_type: Option<String>,
    #[serde(default)]
    pub additional_data: Option<serde_json::Value>,
}

/// 刷新验证请求(tokens 端点)
#[derive(Debug, Clone, Deserialize)]
pub struct TokenRefreshRequest {
    pub token_refresh: String,
}
