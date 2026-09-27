//! 统一错误体系(对齐 Python common/utils/fastapiEX/exceptions.py)
//!
//! 前端契约: 错误响应统一为 {"detail": 文案}; 422 校验错误 detail 为 [{loc,msg,type}]
//! 所有 handler 返回的 Err 均经 AppError → IntoResponse 转换, 杜绝行为漂移。

use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::Json;
use serde::Serialize;

/// 422 校验错误单项(与 FastAPI detail 数组元素同构)
#[derive(Debug, Clone, Serialize)]
pub struct ValidationErrorItem {
    /// 错误位置, 如 ["body","username"] 或 ["query","page"]
    pub loc: Vec<String>,
    /// 人话错误信息
    pub msg: String,
    /// 错误类型标识(如 value_error / missing)
    #[serde(rename = "type")]
    pub error_type: String,
}

/// 统一业务错误(所有模块共用, IntoResponse 输出 {"detail": ...} 或 422 数组)
#[derive(Debug, thiserror::Error)]
pub enum AppError {
    /// 一般业务校验失败 → 400
    #[error("{0}")]
    Business(String),
    /// 未认证 → 401
    #[error("{0}")]
    Unauthorized(String),
    /// 无权限 → 403
    #[error("{0}")]
    Forbidden(String),
    /// 资源不存在 → 404
    #[error("{0}")]
    NotFound(String),
    /// 资源冲突(重名/状态互斥) → 409
    #[error("{0}")]
    Conflict(String),
    /// 请求体校验失败 → 422(FastAPI 校验错误同构)
    #[error("校验失败")]
    Validation(Vec<ValidationErrorItem>),
    /// 上游服务请求失败 → 502(对齐 Python HTTPException(502))
    #[error("{0}")]
    BadGateway(String),
    /// 未处理异常 → 500
    #[error("{0}")]
    Internal(String),
}

impl AppError {
    /// 快捷构造 400
    pub fn business(msg: impl Into<String>) -> Self {
        Self::Business(msg.into())
    }

    /// 快捷构造 404
    pub fn not_found(msg: impl Into<String>) -> Self {
        Self::NotFound(msg.into())
    }

    /// 快捷构造 401
    pub fn unauthorized(msg: impl Into<String>) -> Self {
        Self::Unauthorized(msg.into())
    }

    /// 快捷构造 403
    pub fn forbidden(msg: impl Into<String>) -> Self {
        Self::Forbidden(msg.into())
    }

    /// 快捷构造 409(重名/状态互斥)
    pub fn conflict(msg: impl Into<String>) -> Self {
        Self::Conflict(msg.into())
    }

    /// 快捷构造 500(未处理异常)
    pub fn internal(msg: impl Into<String>) -> Self {
        Self::Internal(msg.into())
    }

    /// 快捷构造 502(上游搜索引擎等请求失败)
    pub fn bad_gateway(msg: impl Into<String>) -> Self {
        Self::BadGateway(msg.into())
    }

    /// 快捷构造 422 校验错误(单字段; 委托模块级 validation 函数)
    pub fn validation(loc: &[&str], msg: impl Into<String>) -> Self {
        validation(loc, msg)
    }

    /// 对应 HTTP 状态码
    pub fn status_code(&self) -> StatusCode {
        match self {
            Self::Business(_) => StatusCode::BAD_REQUEST,
            Self::Unauthorized(_) => StatusCode::UNAUTHORIZED,
            Self::Forbidden(_) => StatusCode::FORBIDDEN,
            Self::NotFound(_) => StatusCode::NOT_FOUND,
            Self::Conflict(_) => StatusCode::CONFLICT,
            Self::Validation(_) => StatusCode::UNPROCESSABLE_ENTITY,
            Self::BadGateway(_) => StatusCode::BAD_GATEWAY,
            Self::Internal(_) => StatusCode::INTERNAL_SERVER_ERROR,
        }
    }
}

/// 简化 Result 书写的别名
impl From<sea_orm::DbErr> for AppError {
    fn from(e: sea_orm::DbErr) -> Self {
        // 数据库错误统一按 500 记录(连接失败/约束冲突等)
        tracing::error!("数据库错误: {e}");
        Self::Internal(format!("数据库错误: {e}"))
    }
}

impl From<serde_json::Error> for AppError {
    fn from(e: serde_json::Error) -> Self {
        Self::Internal(format!("JSON 处理错误: {e}"))
    }
}

impl From<std::io::Error> for AppError {
    fn from(e: std::io::Error) -> Self {
        Self::Internal(format!("文件读写失败: {e}"))
    }
}

impl From<argon2::password_hash::Error> for AppError {
    fn from(e: argon2::password_hash::Error) -> Self {
        Self::Internal(format!("密码处理错误: {e}"))
    }
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let status = self.status_code();
        // 500 打 error 日志, 400 打 warning(对齐 Python 侧日志行为)
        match &self {
            Self::Internal(msg) => tracing::error!("未处理异常(500): {msg}"),
            Self::Business(msg) => tracing::warn!("业务校验失败(400): {msg}"),
            _ => {}
        }
        let body = match &self {
            // 422: detail 为数组(与 FastAPI 校验错误同构, 前端按 loc/msg 拼接)
            Self::Validation(items) => Json(serde_json::json!({ "detail": items })),
            _ => Json(serde_json::json!({ "detail": self.to_string() })),
        };
        let mut response = (status, body).into_response();
        // 401 附 WWW-Authenticate 头(与 Python 侧 OAuth2 行为一致)
        if status == StatusCode::UNAUTHORIZED {
            response
                .headers_mut()
                .insert("WWW-Authenticate", "Bearer".parse().expect("静态头解析"));
        }
        response
    }
}

/// 构造 422 校验错误(单字段便捷入口)
pub fn validation(loc: &[&str], msg: impl Into<String>) -> AppError {
    AppError::Validation(vec![ValidationErrorItem {
        loc: loc.iter().map(|s| s.to_string()).collect(),
        msg: msg.into(),
        error_type: "value_error".to_string(),
    }])
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::to_bytes;

    #[tokio::test]
    async fn 业务错误映射400与detail格式() {
        let response = AppError::Business("用户名已存在".to_string()).into_response();
        assert_eq!(response.status(), StatusCode::BAD_REQUEST);
        let bytes = to_bytes(response.into_body(), 1024).await.unwrap();
        let json: serde_json::Value = serde_json::from_slice(&bytes).unwrap();
        assert_eq!(json["detail"], "用户名已存在");
    }

    #[tokio::test]
    async fn 未授权401附鉴权头() {
        let response = AppError::Unauthorized("令牌无效".to_string()).into_response();
        assert_eq!(response.status(), StatusCode::UNAUTHORIZED);
        assert_eq!(
            response.headers().get("WWW-Authenticate").unwrap(),
            "Bearer"
        );
    }

    #[tokio::test]
    async fn 校验错误映射422数组格式() {
        let err = validation(&["body", "username"], "不能为空");
        let response = err.into_response();
        assert_eq!(response.status(), StatusCode::UNPROCESSABLE_ENTITY);
        let bytes = to_bytes(response.into_body(), 1024).await.unwrap();
        let json: serde_json::Value = serde_json::from_slice(&bytes).unwrap();
        assert_eq!(json["detail"][0]["loc"][0], "body");
        assert_eq!(json["detail"][0]["loc"][1], "username");
        assert_eq!(json["detail"][0]["msg"], "不能为空");
    }
}
