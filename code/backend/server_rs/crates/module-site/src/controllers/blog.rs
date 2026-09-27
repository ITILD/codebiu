//! 博客控制器(对齐 Python module_site/controller/blog.py)
//!
//! 路由前缀 /site/blog/posts: 发布(markdown/url)、管理(仅本人)、展示(仅已发布)。
//! 控制器只做请求解析/权限校验/响应包装, 业务规则与数据读写分别在 services/dao 层。

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::routing::{get, post};
use axum::{Json, Router};
use serde::Deserialize;

use crate::do_::entity::blog_post;
use module_authorization::do_::entity::user;
use module_authorization::deps::{authorize, AuthUser};

use common::utils::extract::{AppJson, AppQuery};
use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::pagination::{PaginationParams, PaginationResponse};

use crate::do_::blog::{BlogPostCreate, BlogPostUpdate};
use crate::services;

/// site:blog 资源权限校验
async fn require_perm(user: &user::Model, act: &str) -> Result<(), AppError> {
    authorize(&user.id, "site", "blog", act).await
}

/// POST "" —— 发布博客文章(201; 返回文章ID)
pub async fn create_blog_post(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppJson(data): AppJson<BlogPostCreate>,
) -> Result<(StatusCode, Json<String>), AppError> {
    require_perm(&actor, "create").await?;
    let id = services::blog::add(&state.db, data, &actor.id).await?;
    Ok((StatusCode::CREATED, Json(id)))
}

/// GET /view/list 查询参数
#[derive(Debug, Deserialize)]
pub struct ViewListQuery {
    /// 标题关键词(最长 100)
    #[serde(default)]
    pub keyword: Option<String>,
}

/// GET /view/list —— 分页查询已发布文章(展示页, 不限归属)
pub async fn list_published_posts(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppQuery(pagination): AppQuery<PaginationParams>,
    AppQuery(query): AppQuery<ViewListQuery>,
) -> Result<Json<PaginationResponse<blog_post::Model>>, AppError> {
    require_perm(&actor, "read").await?;
    pagination.validate()?;
    let page = services::blog::list_published(&state.db, &pagination, query.keyword).await?;
    Ok(Json(page))
}

/// GET /list 查询参数(status/source_type 为别名过滤)
#[derive(Debug, Deserialize)]
pub struct MyListQuery {
    /// 标题模糊搜索(最长 100)
    #[serde(default)]
    pub title: Option<String>,
    /// 状态过滤(查询参数名为 status)
    #[serde(rename = "status")]
    pub status_filter: Option<String>,
    /// 来源过滤(查询参数名为 source_type)
    #[serde(rename = "source_type")]
    pub source_filter: Option<String>,
}

/// GET /list —— 分页查询本人文章列表(管理页)
pub async fn list_my_posts(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppQuery(pagination): AppQuery<PaginationParams>,
    AppQuery(query): AppQuery<MyListQuery>,
) -> Result<Json<PaginationResponse<blog_post::Model>>, AppError> {
    require_perm(&actor, "read").await?;
    pagination.validate()?;
    let page = services::blog::list_mine(
        &state.db,
        &pagination,
        &actor.id,
        query.title,
        query.status_filter,
        query.source_filter,
    )
    .await?;
    Ok(Json(page))
}

/// GET /{post_id} —— 获取单篇文章详情(草稿仅作者可见, 不存在 404)
pub async fn get_blog_post(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(post_id): Path<String>,
) -> Result<Json<blog_post::Model>, AppError> {
    require_perm(&actor, "read").await?;
    services::blog::get_visible(&state.db, &post_id, &actor.id)
        .await?
        .map(Json)
        .ok_or_else(|| AppError::not_found("博客文章不存在"))
}

/// DELETE /{post_id} —— 删除本人文章(204; 不存在或不属于当前用户 404)
pub async fn delete_blog_post(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(post_id): Path<String>,
) -> Result<StatusCode, AppError> {
    require_perm(&actor, "delete").await?;
    services::blog::delete(&state.db, &post_id, &actor.id).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// PUT /{post_id} —— 更新本人文章(204; 仅显式传入的字段生效; 不存在 404)
pub async fn update_blog_post(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(post_id): Path<String>,
    AppJson(data): AppJson<BlogPostUpdate>,
) -> Result<StatusCode, AppError> {
    require_perm(&actor, "update").await?;
    services::blog::update(&state.db, &post_id, data, &actor.id).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// 博客子路由(nest 到 /site/blog/posts 前缀)
pub fn router() -> Router<AppState> {
    Router::new()
        .route("/", post(create_blog_post))
        .route("/view/list", get(list_published_posts))
        .route("/list", get(list_my_posts))
        .route(
            "/{post_id}",
            get(get_blog_post).delete(delete_blog_post).put(update_blog_post),
        )
}
