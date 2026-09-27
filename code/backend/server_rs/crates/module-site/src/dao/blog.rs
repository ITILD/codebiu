//! 博客文章数据访问(对齐 Python module_site/dao/blog.py)
//!
//! 写操作全部按 user_id 归属隔离; 不命中即 404(与 Python NotFoundError 语义一致)。

use sea_orm::sea_query::Expr;
use sea_orm::{
    ActiveModelTrait, ColumnTrait, DatabaseConnection, EntityTrait, PaginatorTrait, QueryFilter,
    QueryOrder, QuerySelect, Select, Set,
};
use uuid::Uuid;

use crate::do_::entity::blog_post;

use common::utils::error::AppError;
use common::utils::pagination::PaginationParams;

use crate::do_::blog::{BlogPostCreate, BlogPostUpdate, PostStatus};
use crate::do_::now_utc;

/// 新增博客文章记录
///
/// :param post: 文章创建数据
/// :param user_id: 作者用户ID
/// :return: 新创建文章ID
pub async fn add(
    db: &DatabaseConnection,
    post: BlogPostCreate,
    user_id: &str,
) -> Result<String, AppError> {
    let id = Uuid::new_v4().simple().to_string();
    let am = blog_post::ActiveModel {
        title: Set(post.title),
        // 未传字段取 Python 模型默认值(content 默认空串, 非 NULL)
        source_type: Set(post.source_type.unwrap_or_default().as_str().to_string()),
        content: Set(Some(post.content.unwrap_or_default())),
        url: Set(post.url),
        category: Set(post.category),
        status: Set(post.status.unwrap_or(PostStatus::Draft).as_str().to_string()),
        id: Set(id.clone()),
        user_id: Set(user_id.to_string()),
        created_at: Set(Some(now_utc())),
        updated_at: Set(now_utc()),
    };
    am.insert(db).await?;
    Ok(id)
}

/// 查询单篇文章(不限归属, 由服务层按展示语义判定可见性)
pub async fn get(
    db: &DatabaseConnection,
    post_id: &str,
) -> Result<Option<blog_post::Model>, AppError> {
    Ok(blog_post::Entity::find_by_id(post_id.to_owned())
        .one(db)
        .await?)
}

/// 直接更新本人文章记录(不先查询, 仅显式传入字段生效)
///
/// :raises: AppError::not_found 文章不存在或不属于当前用户
pub async fn update(
    db: &DatabaseConnection,
    post_id: &str,
    post: BlogPostUpdate,
    user_id: &str,
) -> Result<(), AppError> {
    // updated_at 由 onupdate 语义自动刷新(此处显式 Set)
    let mut update = blog_post::Entity::update_many()
        .col_expr(blog_post::Column::UpdatedAt, Expr::value(now_utc()));
    if let Some(v) = post.title {
        update = update.col_expr(blog_post::Column::Title, Expr::value(v));
    }
    if let Some(v) = post.source_type {
        update = update.col_expr(
            blog_post::Column::SourceType,
            Expr::value(v.as_str().to_string()),
        );
    }
    if let Some(v) = post.content {
        update = update.col_expr(blog_post::Column::Content, Expr::value(v));
    }
    if let Some(v) = post.url {
        update = update.col_expr(blog_post::Column::Url, Expr::value(v));
    }
    if let Some(v) = post.category {
        update = update.col_expr(blog_post::Column::Category, Expr::value(v));
    }
    if let Some(v) = post.status {
        update = update.col_expr(
            blog_post::Column::Status,
            Expr::value(v.as_str().to_string()),
        );
    }
    let result = update
        .filter(blog_post::Column::Id.eq(post_id))
        .filter(blog_post::Column::UserId.eq(user_id))
        .exec(db)
        .await?;
    if result.rows_affected == 0 {
        return Err(AppError::not_found(format!(
            "未找到ID为 {post_id} 的博客文章"
        )));
    }
    Ok(())
}

/// 删除本人文章
///
/// :raises: AppError::not_found 文章不存在或不属于当前用户
pub async fn delete(db: &DatabaseConnection, post_id: &str, user_id: &str) -> Result<(), AppError> {
    let result = blog_post::Entity::delete_many()
        .filter(blog_post::Column::Id.eq(post_id))
        .filter(blog_post::Column::UserId.eq(user_id))
        .exec(db)
        .await?;
    if result.rows_affected == 0 {
        return Err(AppError::not_found(format!(
            "未找到ID为 {post_id} 的博客文章"
        )));
    }
    Ok(())
}

/// 本人文章列表查询(标题模糊/状态/来源过滤, 列表与计数共用)
fn mine_select(
    user_id: &str,
    title: Option<&str>,
    status: Option<&str>,
    source_type: Option<&str>,
) -> Select<blog_post::Entity> {
    let mut select = blog_post::Entity::find().filter(blog_post::Column::UserId.eq(user_id));
    if let Some(t) = title {
        select = select.filter(blog_post::Column::Title.contains(t));
    }
    if let Some(s) = status {
        select = select.filter(blog_post::Column::Status.eq(s));
    }
    if let Some(s) = source_type {
        select = select.filter(blog_post::Column::SourceType.eq(s));
    }
    select
}

/// 分页查询本人文章列表(支持标题模糊/状态/来源过滤, 按创建时间倒序)
pub async fn list_mine(
    db: &DatabaseConnection,
    pagination: &PaginationParams,
    user_id: &str,
    title: Option<&str>,
    status: Option<&str>,
    source_type: Option<&str>,
) -> Result<Vec<blog_post::Model>, AppError> {
    Ok(mine_select(user_id, title, status, source_type)
        .order_by_desc(blog_post::Column::CreatedAt)
        .offset(pagination.offset())
        .limit(pagination.limit())
        .all(db)
        .await?)
}

/// 统计本人文章总数(与列表过滤条件一致)
pub async fn count_mine(
    db: &DatabaseConnection,
    user_id: &str,
    title: Option<&str>,
    status: Option<&str>,
    source_type: Option<&str>,
) -> Result<i64, AppError> {
    let total = mine_select(user_id, title, status, source_type)
        .count(db)
        .await?;
    Ok(total as i64)
}

/// 已发布文章查询(展示页公开内容, 列表与计数共用)
fn published_select(keyword: Option<&str>) -> Select<blog_post::Entity> {
    let mut select = blog_post::Entity::find()
        .filter(blog_post::Column::Status.eq(PostStatus::Published.as_str()));
    if let Some(kw) = keyword {
        select = select.filter(blog_post::Column::Title.contains(kw));
    }
    select
}

/// 分页查询全部已发布文章(展示页, 按更新时间倒序)
pub async fn list_published(
    db: &DatabaseConnection,
    pagination: &PaginationParams,
    keyword: Option<&str>,
) -> Result<Vec<blog_post::Model>, AppError> {
    Ok(published_select(keyword)
        .order_by_desc(blog_post::Column::UpdatedAt)
        .offset(pagination.offset())
        .limit(pagination.limit())
        .all(db)
        .await?)
}

/// 统计已发布文章总数
pub async fn count_published(
    db: &DatabaseConnection,
    keyword: Option<&str>,
) -> Result<i64, AppError> {
    let total = published_select(keyword).count(db).await?;
    Ok(total as i64)
}
