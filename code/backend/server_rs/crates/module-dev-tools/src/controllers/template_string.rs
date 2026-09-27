//! 模板字符串控制器(对齐 Python module_dev_tools/controller/template_string.py)
//!
//! 路由前缀 /dev-tools/template-strings: 创建(带语法校验) / 分页 / 滚动 / 详情 /
//! 删除 / 更新(带语法校验) / 渲染 / 语法校验。
//! 控制器只做请求解析/权限校验/响应包装, 业务规则与数据读写分别在 services/dao 层。

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::routing::{get, post};
use axum::{Json, Router};
use serde::Deserialize;

use crate::do_::entity::template_string;
use module_authorization::do_::entity::user;
use module_authorization::deps::{authorize, AuthUser};

use common::utils::extract::{AppJson, AppQuery};
use common::runtime::AppState;
use common::utils::error::{AppError, ValidationErrorItem};
use common::utils::pagination::{
    InfiniteScrollParams, InfiniteScrollResponse, PaginationParams, PaginationResponse,
};

use crate::do_::template_string::{
    TemplateRenderRequest, TemplateRenderResponse, TemplateStringCreate, TemplateStringUpdate,
    TemplateValidateResponse,
};
use crate::services;

/// dev_tools:template_string 资源权限校验
async fn require_perm(user: &user::Model, act: &str) -> Result<(), AppError> {
    authorize(&user.id, "dev_tools", "template_string", act).await
}

/// POST "" —— 创建模板字符串(201; 语法无效时 400)
pub async fn create_template_string(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppJson(data): AppJson<TemplateStringCreate>,
) -> Result<(StatusCode, Json<String>), AppError> {
    require_perm(&actor, "create").await?;
    let id = services::template_string::add(&state.db, data).await?;
    Ok((StatusCode::CREATED, Json(id)))
}

/// GET /scroll —— 无限滚动查询模板字符串
pub async fn infinite_scroll(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppQuery(params): AppQuery<InfiniteScrollParams>,
) -> Result<Json<InfiniteScrollResponse<template_string::Model>>, AppError> {
    require_perm(&actor, "read").await?;
    let page = services::template_string::scroll(&state.db, &params).await?;
    Ok(Json(page))
}

/// GET /list —— 分页查询模板字符串列表(不做条件过滤, total 为全表总数)
pub async fn list_template_strings(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppQuery(pagination): AppQuery<PaginationParams>,
) -> Result<Json<PaginationResponse<template_string::Model>>, AppError> {
    require_perm(&actor, "read").await?;
    pagination.validate()?;
    let page = services::template_string::list_paged(&state.db, &pagination).await?;
    Ok(Json(page))
}

/// GET /{template_string_id} —— 获取单个模板字符串(不存在 404 "模板字符串不存在")
pub async fn get_template_string(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(template_string_id): Path<String>,
) -> Result<Json<template_string::Model>, AppError> {
    require_perm(&actor, "read").await?;
    services::template_string::get(&state.db, &template_string_id)
        .await?
        .map(Json)
        .ok_or_else(|| AppError::not_found("模板字符串不存在"))
}

/// DELETE /{template_string_id} —— 删除模板字符串(204; 不存在 404)
pub async fn delete_template_string(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(template_string_id): Path<String>,
) -> Result<StatusCode, AppError> {
    require_perm(&actor, "delete").await?;
    services::template_string::delete(&state.db, &template_string_id).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// PUT /{template_string_id} —— 更新模板字符串(204; 语法无效 400; 不存在 404)
pub async fn update_template_string(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(template_string_id): Path<String>,
    AppJson(data): AppJson<TemplateStringUpdate>,
) -> Result<StatusCode, AppError> {
    require_perm(&actor, "update").await?;
    services::template_string::update(&state.db, &template_string_id, data).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// POST /render —— 渲染模板(优先用请求体内容, 未提供内容时按ID读库)
pub async fn render_template(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppJson(request): AppJson<TemplateRenderRequest>,
) -> Result<Json<TemplateRenderResponse>, AppError> {
    require_perm(&actor, "render").await?;
    let response = services::template_string::render(&state.db, request).await?;
    Ok(Json(response))
}

/// POST /validate —— 校验模板语法并提取 ${var} 变量列表(query 参数 template_content)
pub async fn validate_template_syntax_endpoint(
    AuthUser(actor): AuthUser,
    AppQuery(query): AppQuery<ValidateQuery>,
) -> Result<Json<TemplateValidateResponse>, AppError> {
    require_perm(&actor, "validate").await?;
    let template_content = required_query(&query.template_content, "template_content")?;
    let response = services::template_string::validate(&template_content).await?;
    Ok(Json(response))
}

/// validate 端点查询参数(对齐 Python 裸 str 参数 → query 注入)
#[derive(Debug, Deserialize)]
pub struct ValidateQuery {
    /// 模板内容
    #[serde(default)]
    pub template_content: Option<String>,
}

/// 必填查询参数校验(缺失构造 422, type=missing 与 FastAPI 一致)
fn required_query(value: &Option<String>, field: &str) -> Result<String, AppError> {
    value.clone().ok_or_else(|| {
        AppError::Validation(vec![ValidationErrorItem {
            loc: vec!["query".to_string(), field.to_string()],
            msg: "Field required".to_string(),
            error_type: "missing".to_string(),
        }])
    })
}

/// 模板字符串子路由(nest 到 /dev-tools/template-strings 前缀)
pub fn router() -> Router<AppState> {
    Router::new()
        .route("/", post(create_template_string))
        .route("/scroll", get(infinite_scroll))
        .route("/list", get(list_template_strings))
        .route("/render", post(render_template))
        .route("/validate", post(validate_template_syntax_endpoint))
        .route(
            "/{template_string_id}",
            get(get_template_string)
                .delete(delete_template_string)
                .put(update_template_string),
        )
}
