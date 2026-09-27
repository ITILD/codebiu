//! 令牌管理控制器(对齐 Python controller/token.py)
//!
//! 路由前缀 /authorization/tokens: 令牌创建/刷新/验证/批量撤销/查询。
//! 说明: 与 Python 一致, 本组端点不挂鉴权依赖。

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::Json;
use serde::Deserialize;
use serde_json::{json, Value};

use crate::do_::auth::TokenResponseBase;
use crate::do_::token::{TokenCreateRequest, TokenRefreshRequest};
use crate::services::token as token_svc;
use common::utils::extract::{AppJson, AppQuery};
use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::security::jwt::TokenType;
use crate::do_::entity::token;

/// token_access 查询参数(verify/info 共用)
#[derive(Debug, Deserialize)]
pub struct TokenAccessQuery {
    #[serde(default)]
    pub token_access: Option<String>,
}

/// POST /create —— 创建令牌(201; token_type 默认 access; refresh 落库返回 token_id)
pub async fn create_token(
    state: State<AppState>,
    AppJson(req): AppJson<TokenCreateRequest>,
) -> Result<(StatusCode, Json<TokenResponseBase>), AppError> {
    let config = token_svc::token_config(&state.settings).await?;
    let token_type = match req.token_type.as_deref() {
        Some("refresh") => TokenType::Refresh,
        _ => TokenType::Access,
    };
    let resp = token_svc::create_token_response(
        &state.db,
        &config,
        &req.user_id,
        token_type,
        req.additional_data.unwrap_or(Value::Null),
    )
    .await?;
    Ok((StatusCode::CREATED, Json(resp)))
}

/// POST /refresh —— 使用刷新令牌获取新的访问令牌(失败 400 "Invalid refresh token: ...")
pub async fn token_refresh(
    state: State<AppState>,
    AppJson(req): AppJson<TokenRefreshRequest>,
) -> Result<Json<TokenResponseBase>, AppError> {
    let config = token_svc::token_config(&state.settings).await?;
    // 验证刷新令牌(查库确认未撤销)后签发新访问令牌
    let payload = token_svc::verify(&state.db, &config, &req.token_refresh, TokenType::Refresh)
        .await
        .map_err(|e| AppError::business(format!("Invalid refresh token: {e}")))?;
    let access = token_svc::create_token_response(
        &state.db,
        &config,
        &payload.sub,
        TokenType::Access,
        Value::Null,
    )
    .await?;
    Ok(Json(access))
}

/// POST /verify?token_access= —— 验证访问令牌(有效返回载荷; 无效 401)
pub async fn verify_token(
    state: State<AppState>,
    AppQuery(q): AppQuery<TokenAccessQuery>,
) -> Result<Json<Value>, AppError> {
    let token = q
        .token_access
        .ok_or_else(|| AppError::business("Missing token_access parameter"))?;
    let config = token_svc::token_config(&state.settings).await?;
    let payload = token_svc::verify(&state.db, &config, &token, TokenType::Access)
        .await
        .map_err(|e| AppError::unauthorized(format!("Invalid token: {e}")))?;
    Ok(Json(json!({ "valid": true, "payload": payload })))
}

/// DELETE /revoke-all/{user_id} —— 撤销用户所有令牌(强制重新登录)
pub async fn revoke_all_tokens(
    state: State<AppState>,
    Path(user_id): Path<String>,
) -> Result<Json<Value>, AppError> {
    token_svc::delete_by_user_id(&state.db, &user_id).await?;
    Ok(Json(json!({ "success": true })))
}

/// GET /info?token_access= —— 获取令牌在数据库中的完整信息(refresh 记录; 无 404)
pub async fn get_token_info(
    state: State<AppState>,
    AppQuery(q): AppQuery<TokenAccessQuery>,
) -> Result<Json<token::Model>, AppError> {
    let token = q
        .token_access
        .ok_or_else(|| AppError::business("Missing token_access parameter"))?;
    let config = token_svc::token_config(&state.settings).await?;
    let payload = token_svc::verify(&state.db, &config, &token, TokenType::Access)
        .await
        .map_err(|e| AppError::unauthorized(format!("Invalid token: {e}")))?;
    if payload.sub.is_empty() {
        return Err(AppError::unauthorized("Invalid token: missing 'sub'"));
    }
    let info = token_svc::get_by_token(&state.db, &token)
        .await
        .ok_or_else(|| AppError::not_found("令牌不存在"))?;
    Ok(Json(info))
}

/// 令牌管理路由(挂载到 /authorization/tokens)
pub fn router() -> axum::Router<common::runtime::AppState> {
    use axum::routing::{delete, get, post};
    axum::Router::new()
        .route("/create", post(create_token))
        .route("/refresh", post(token_refresh))
        .route("/verify", post(verify_token))
        .route("/revoke-all/{user_id}", delete(revoke_all_tokens))
        .route("/info", get(get_token_info))
}
