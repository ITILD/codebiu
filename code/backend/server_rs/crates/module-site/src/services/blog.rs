//! 博客文章服务: 发布(在线 markdown/关联 URL)、管理与展示

use sea_orm::DatabaseConnection;

use crate::do_::entity::blog_post;

use common::utils::error::AppError;
use common::utils::pagination::{PaginationParams, PaginationResponse};

use crate::dao;
use crate::do_::blog::{BlogPostCreate, BlogPostUpdate, PostStatus};

/// 新增文章(归属当前用户)
///
/// :return: 新建文章ID
pub async fn add(
    db: &DatabaseConnection,
    post: BlogPostCreate,
    user_id: &str,
) -> Result<String, AppError> {
    dao::blog::add(db, post, user_id).await
}

/// 查询单篇文章(带可见性判定)
///
/// 已发布文章对持有 read 权限的用户可见; 草稿仅作者可见。
pub async fn get_visible(
    db: &DatabaseConnection,
    post_id: &str,
    user_id: &str,
) -> Result<Option<blog_post::Model>, AppError> {
    let result = dao::blog::get(db, post_id).await?;
    Ok(result.filter(|p| {
        p.user_id == user_id || p.status == PostStatus::Published.as_str()
    }))
}

/// 更新本人文章
pub async fn update(
    db: &DatabaseConnection,
    post_id: &str,
    post: BlogPostUpdate,
    user_id: &str,
) -> Result<(), AppError> {
    dao::blog::update(db, post_id, post, user_id).await
}

/// 删除本人文章
pub async fn delete(
    db: &DatabaseConnection,
    post_id: &str,
    user_id: &str,
) -> Result<(), AppError> {
    dao::blog::delete(db, post_id, user_id).await
}

/// 分页获取本人文章列表(管理页)
pub async fn list_mine(
    db: &DatabaseConnection,
    pagination: &PaginationParams,
    user_id: &str,
    title: Option<String>,
    status: Option<String>,
    source_type: Option<String>,
) -> Result<PaginationResponse<blog_post::Model>, AppError> {
    let items = dao::blog::list_mine(
        db,
        pagination,
        user_id,
        title.as_deref(),
        status.as_deref(),
        source_type.as_deref(),
    )
    .await?;
    let total = dao::blog::count_mine(
        db,
        user_id,
        title.as_deref(),
        status.as_deref(),
        source_type.as_deref(),
    )
    .await?;
    Ok(PaginationResponse::create(items, total, pagination))
}

/// 分页获取已发布文章列表(展示页)
pub async fn list_published(
    db: &DatabaseConnection,
    pagination: &PaginationParams,
    keyword: Option<String>,
) -> Result<PaginationResponse<blog_post::Model>, AppError> {
    let items = dao::blog::list_published(db, pagination, keyword.as_deref()).await?;
    let total = dao::blog::count_published(db, keyword.as_deref()).await?;
    Ok(PaginationResponse::create(items, total, pagination))
}
