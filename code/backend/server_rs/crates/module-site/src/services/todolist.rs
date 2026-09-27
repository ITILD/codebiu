//! 备忘服务: 编辑管理 + 日历展示数据源

use chrono::{DateTime, FixedOffset};
use sea_orm::DatabaseConnection;

use crate::do_::entity::todo_list;

use common::utils::error::AppError;
use common::utils::pagination::{PaginationParams, PaginationResponse};

use crate::dao;
use crate::do_::todolist::{TodolistCreate, TodolistUpdate};

/// 新增备忘(归属当前用户)
///
/// :return: 新建备忘ID
pub async fn add(
    db: &DatabaseConnection,
    data: TodolistCreate,
    user_id: &str,
) -> Result<String, AppError> {
    dao::todolist::add(db, data, user_id).await
}

/// 更新本人备忘
pub async fn update(
    db: &DatabaseConnection,
    todolist_id: &str,
    data: TodolistUpdate,
    user_id: &str,
) -> Result<(), AppError> {
    dao::todolist::update(db, todolist_id, data, user_id).await
}

/// 删除本人备忘
pub async fn delete(
    db: &DatabaseConnection,
    todolist_id: &str,
    user_id: &str,
) -> Result<(), AppError> {
    dao::todolist::delete(db, todolist_id, user_id).await
}

/// 查询单个备忘(仅本人可见; NULL 归属的存量数据对持有 read 权限的用户可见)
pub async fn get(
    db: &DatabaseConnection,
    todolist_id: &str,
    user_id: &str,
) -> Result<Option<todo_list::Model>, AppError> {
    let result = dao::todolist::get(db, todolist_id).await?;
    Ok(result.filter(|t| t.user_id.as_ref().map(|uid| uid == user_id).unwrap_or(true)))
}

/// 分页获取本人备忘列表(管理页)
pub async fn list_mine(
    db: &DatabaseConnection,
    pagination: &PaginationParams,
    user_id: &str,
    name: Option<String>,
    status: Option<String>,
) -> Result<PaginationResponse<todo_list::Model>, AppError> {
    let items = dao::todolist::list_mine(db, pagination, user_id, name.as_deref(), status.as_deref())
        .await?;
    let total = dao::todolist::count_mine(db, user_id, name.as_deref(), status.as_deref()).await?;
    Ok(PaginationResponse::create(items, total, pagination))
}

/// 获取时间范围内的本人备忘(日历 年/月/周 视图数据源)
pub async fn list_in_range(
    db: &DatabaseConnection,
    user_id: &str,
    start: DateTime<FixedOffset>,
    end: DateTime<FixedOffset>,
) -> Result<Vec<todo_list::Model>, AppError> {
    dao::todolist::list_in_range(db, user_id, start, end).await
}
