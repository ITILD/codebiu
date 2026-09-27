//! 模板控制器(对齐 Python module_template/controller/template.py)
//!
//! 路由前缀 /template/templates: 创建 / 分页 / 无限滚动 / 详情 / 删除 / 批量删除 / 更新。
//! 控制器只做请求解析/权限校验/响应包装, 业务规则与数据读写分别在 services/dao 层。

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::routing::{get, post};
use axum::{Json, Router};

use crate::do_::entity::template;
use module_authorization::do_::entity::user;
use module_authorization::deps::{authorize, AuthUser};

use common::utils::extract::{AppJson, AppQuery};
use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::pagination::{
    InfiniteScrollParams, InfiniteScrollResponse, PaginationParams, PaginationResponse,
};

use crate::do_::template::{TemplateBatchDelete, TemplateCreate, TemplateUpdate};
use crate::services;

/// template:template 资源权限校验
async fn require_perm(user: &user::Model, act: &str) -> Result<(), AppError> {
    authorize(&user.id, "template", "template", act).await
}

/// POST "" —— 创建模板(201; 返回模板ID)
pub async fn create_template(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppJson(data): AppJson<TemplateCreate>,
) -> Result<(StatusCode, Json<String>), AppError> {
    require_perm(&actor, "create").await?;
    let id = services::template::add(&state.db, data).await?;
    Ok((StatusCode::CREATED, Json(id)))
}

/// GET /scroll —— 无限滚动查询(先查最新, 滚下拉取更早数据; 默认按 created_at)
pub async fn infinite_scroll(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppQuery(params): AppQuery<InfiniteScrollParams>,
) -> Result<Json<InfiniteScrollResponse<template::Model>>, AppError> {
    require_perm(&actor, "read").await?;
    let page = services::template::scroll(&state.db, &params).await?;
    Ok(Json(page))
}

/// GET /list —— 分页查询模板列表(不做任何条件过滤, total 为全表总数)
pub async fn list_templates(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppQuery(pagination): AppQuery<PaginationParams>,
) -> Result<Json<PaginationResponse<template::Model>>, AppError> {
    require_perm(&actor, "read").await?;
    pagination.validate()?;
    let page = services::template::list_paged(&state.db, &pagination).await?;
    Ok(Json(page))
}

/// GET /{template_id} —— 获取单个模板详情(不存在 404 "模板不存在")
pub async fn get_template(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(template_id): Path<String>,
) -> Result<Json<template::Model>, AppError> {
    require_perm(&actor, "read").await?;
    services::template::get(&state.db, &template_id)
        .await?
        .map(Json)
        .ok_or_else(|| AppError::not_found("模板不存在"))
}

/// DELETE /{template_id} —— 删除模板(204; 不存在 404)
pub async fn delete_template(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(template_id): Path<String>,
) -> Result<StatusCode, AppError> {
    require_perm(&actor, "delete").await?;
    services::template::delete(&state.db, &template_id).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// DELETE /batch —— 批量删除模板(不存在的ID静默跳过, 返回实际删除数量)
pub async fn batch_delete_template(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppJson(batch_delete): AppJson<TemplateBatchDelete>,
) -> Result<Json<serde_json::Value>, AppError> {
    require_perm(&actor, "delete").await?;
    batch_delete.validate()?;
    let deleted_count = services::template::batch_delete(&state.db, batch_delete.ids).await?;
    Ok(Json(serde_json::json!({ "deleted_count": deleted_count })))
}

/// PUT /{template_id} —— 更新模板(204; 仅显式传入字段生效; 不存在 404)
pub async fn update_template(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(template_id): Path<String>,
    AppJson(data): AppJson<TemplateUpdate>,
) -> Result<StatusCode, AppError> {
    require_perm(&actor, "update").await?;
    services::template::update(&state.db, &template_id, data).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// 模板子路由(nest 到 /template/templates 前缀)
pub fn router() -> Router<AppState> {
    Router::new()
        .route("/", post(create_template))
        .route("/scroll", get(infinite_scroll))
        .route("/list", get(list_templates))
        .route("/batch", axum::routing::delete(batch_delete_template))
        .route(
            "/{template_id}",
            get(get_template).delete(delete_template).put(update_template),
        )
}
