//! 系统通用动态配置管理端点(对齐 Python controller/sys_config.py; 前缀 /sys-configs)
//!
//! 权限: main:config:read / main:config:update(通用配置为管理员专属)

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::routing::get;
use axum::{Json, Router};
use module_authorization::do_::entity::user;

use module_authorization::deps::{authorize, AuthUser};

use common::utils::extract::AppJson;
use common::runtime::AppState;
use common::utils::error::AppError;

use crate::do_::sys_config::ConfigUpdateRequest;

/// main:config 资源权限校验(全部端点共用)
async fn require_perm(user: &user::Model, act: &str) -> Result<(), AppError> {
    authorize(&user.id, "main", "config", act).await
}

/// GET "" —— 获取全部配置组(元数据 + 打码值; 结构直接驱动前端通用配置表单)
pub async fn list_sys_configs(
    State(state): State<AppState>,
    AuthUser(user): AuthUser,
) -> Result<Json<serde_json::Value>, AppError> {
    require_perm(&user, "read").await?;
    let groups = state.settings.describe_all().await?;
    Ok(Json(serde_json::json!({ "groups": groups })))
}

/// GET /{group} —— 获取单个配置组(未知组名 400)
pub async fn get_sys_config(
    State(state): State<AppState>,
    AuthUser(user): AuthUser,
    Path(group): Path<String>,
) -> Result<Json<serde_json::Value>, AppError> {
    require_perm(&user, "read").await?;
    Ok(Json(state.settings.describe(&group).await?))
}

/// PUT /{group} —— 更新配置组(204; 校验通过后落库并使缓存失效)
pub async fn update_sys_config(
    State(state): State<AppState>,
    AuthUser(user): AuthUser,
    Path(group): Path<String>,
    AppJson(body): AppJson<ConfigUpdateRequest>,
) -> Result<StatusCode, AppError> {
    require_perm(&user, "update").await?;
    state.settings.update(&group, &body.data, &user.id).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// 系统配置子路由(nest 到 /sys-configs 前缀)
pub fn router() -> Router<AppState> {
    Router::new()
        .route("/", get(list_sys_configs))
        .route("/{group}", get(get_sys_config).put(update_sys_config))
}
