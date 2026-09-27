//! 备忘控制器(对齐 Python module_site/controller/todolist.py)
//!
//! 路由前缀 /site/todolists: 编辑管理 + 日历展示数据源(/range)。
//! 归属隔离: 存量 user_id 为 NULL 的记录任何持有 read 权限的用户可见(与 Python 一致)。

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::routing::{get, post};
use axum::{Json, Router};
use chrono::{DateTime, FixedOffset};
use serde::Deserialize;

use crate::do_::entity::todo_list;
use module_authorization::do_::entity::user;
use module_authorization::deps::{authorize, AuthUser};

use common::utils::extract::{AppJson, AppQuery};
use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::pagination::{PaginationParams, PaginationResponse};

use crate::do_::todolist::{TodolistCreate, TodolistUpdate};
use crate::services;

/// site:memo 资源权限校验
async fn require_perm(user: &user::Model, act: &str) -> Result<(), AppError> {
    authorize(&user.id, "site", "memo", act).await
}

/// POST "" —— 创建备忘(201; 返回备忘ID)
pub async fn create_todolist(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppJson(data): AppJson<TodolistCreate>,
) -> Result<(StatusCode, Json<String>), AppError> {
    require_perm(&actor, "create").await?;
    let id = services::todolist::add(&state.db, data, &actor.id).await?;
    Ok((StatusCode::CREATED, Json(id)))
}

/// GET /range 查询参数(带时区的 ISO 时间)
#[derive(Debug, Deserialize)]
pub struct RangeQuery {
    /// 范围起始(含)
    pub start: DateTime<FixedOffset>,
    /// 范围结束(不含)
    pub end: DateTime<FixedOffset>,
}

/// GET /range —— 按时间范围查询备忘(日历 年/月/周 视图数据源)
pub async fn list_memos_by_range(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppQuery(query): AppQuery<RangeQuery>,
) -> Result<Json<Vec<todo_list::Model>>, AppError> {
    require_perm(&actor, "read").await?;
    let items =
        services::todolist::list_in_range(&state.db, &actor.id, query.start, query.end).await?;
    Ok(Json(items))
}

/// GET /list 查询参数(status 为别名过滤)
#[derive(Debug, Deserialize)]
pub struct MyListQuery {
    /// 备忘标题模糊搜索(最长 100)
    #[serde(default)]
    pub name: Option<String>,
    /// 状态过滤(查询参数名为 status)
    #[serde(rename = "status")]
    pub status_filter: Option<String>,
}

/// GET /list —— 分页查询本人备忘列表(管理页)
pub async fn list_todolists(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppQuery(pagination): AppQuery<PaginationParams>,
    AppQuery(query): AppQuery<MyListQuery>,
) -> Result<Json<PaginationResponse<todo_list::Model>>, AppError> {
    require_perm(&actor, "read").await?;
    pagination.validate()?;
    let page = services::todolist::list_mine(
        &state.db,
        &pagination,
        &actor.id,
        query.name,
        query.status_filter,
    )
    .await?;
    Ok(Json(page))
}

/// GET /{todolist_id} —— 获取单个备忘(仅本人可见, 不存在 404)
pub async fn get_todolist(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(todolist_id): Path<String>,
) -> Result<Json<todo_list::Model>, AppError> {
    require_perm(&actor, "read").await?;
    services::todolist::get(&state.db, &todolist_id, &actor.id)
        .await?
        .map(Json)
        .ok_or_else(|| AppError::not_found("备忘不存在"))
}

/// DELETE /{todolist_id} —— 删除本人备忘(204; 不存在 404)
pub async fn delete_todolist(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(todolist_id): Path<String>,
) -> Result<StatusCode, AppError> {
    require_perm(&actor, "delete").await?;
    services::todolist::delete(&state.db, &todolist_id, &actor.id).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// PUT /{todolist_id} —— 更新本人备忘(204; 仅显式传入的字段生效; 不存在 404)
pub async fn update_todolist(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(todolist_id): Path<String>,
    AppJson(data): AppJson<TodolistUpdate>,
) -> Result<StatusCode, AppError> {
    require_perm(&actor, "update").await?;
    services::todolist::update(&state.db, &todolist_id, data, &actor.id).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// 备忘子路由(nest 到 /site/todolists 前缀)
pub fn router() -> Router<AppState> {
    Router::new()
        .route("/", post(create_todolist))
        .route("/range", get(list_memos_by_range))
        .route("/list", get(list_todolists))
        .route(
            "/{todolist_id}",
            get(get_todolist).delete(delete_todolist).put(update_todolist),
        )
}
