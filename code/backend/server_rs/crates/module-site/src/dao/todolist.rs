//! 备忘数据访问(对齐 Python module_site/dao/todolist.py)
//!
//! 可见性特殊约定: 存量 user_id 为 NULL 的记录对任何持有 read 权限的用户可见(与 Python 一致)。

use chrono::{DateTime, FixedOffset};
use sea_orm::sea_query::Expr;
use sea_orm::{
    ActiveModelTrait, ColumnTrait, DatabaseConnection, EntityTrait, PaginatorTrait, QueryFilter,
    QueryOrder, QuerySelect, Select, Set,
};
use uuid::Uuid;

use crate::do_::entity::todo_list;

use common::utils::error::AppError;
use common::utils::pagination::PaginationParams;

use crate::do_::now_utc;
use crate::do_::todolist::{TodolistCreate, TodolistUpdate};

/// 新增备忘记录(归属当前用户)
///
/// :return: 新建备忘ID
pub async fn add(
    db: &DatabaseConnection,
    data: TodolistCreate,
    user_id: &str,
) -> Result<String, AppError> {
    let id = Uuid::new_v4().simple().to_string();
    let am = todo_list::ActiveModel {
        // 未传字段取 Python 模型默认值
        name: Set(data.name),
        value: Set(data.value.unwrap_or_default()),
        description: Set(data.description),
        start_at: Set(Some(data.start_at.unwrap_or_else(now_utc))),
        end_at: Set(data.end_at),
        status: Set(data.status.unwrap_or_default().as_str().to_string()),
        pid: Set(None),
        id: Set(id.clone()),
        user_id: Set(Some(user_id.to_string())),
        created_at: Set(Some(now_utc())),
        updated_at: Set(now_utc()),
    };
    am.insert(db).await?;
    Ok(id)
}

/// 查询单个备忘(不限归属, 由服务层判定可见性)
pub async fn get(
    db: &DatabaseConnection,
    todolist_id: &str,
) -> Result<Option<todo_list::Model>, AppError> {
    Ok(todo_list::Entity::find_by_id(todolist_id.to_owned())
        .one(db)
        .await?)
}

/// 直接更新本人备忘记录(不先查询, 仅显式传入字段生效)
///
/// 注: 存量 NULL 归属记录更新会因 user_id 过滤不命中而 404(与 Python 一致)。
pub async fn update(
    db: &DatabaseConnection,
    todolist_id: &str,
    data: TodolistUpdate,
    user_id: &str,
) -> Result<(), AppError> {
    let mut update = todo_list::Entity::update_many()
        .col_expr(todo_list::Column::UpdatedAt, Expr::value(now_utc()));
    if let Some(v) = data.name {
        update = update.col_expr(todo_list::Column::Name, Expr::value(v));
    }
    if let Some(v) = data.value {
        update = update.col_expr(todo_list::Column::Value, Expr::value(v));
    }
    if let Some(v) = data.description {
        update = update.col_expr(todo_list::Column::Description, Expr::value(v));
    }
    if let Some(v) = data.start_at {
        update = update.col_expr(todo_list::Column::StartAt, Expr::value(v));
    }
    if let Some(v) = data.end_at {
        update = update.col_expr(todo_list::Column::EndAt, Expr::value(v));
    }
    if let Some(v) = data.status {
        update = update.col_expr(
            todo_list::Column::Status,
            Expr::value(v.as_str().to_string()),
        );
    }
    let result = update
        .filter(todo_list::Column::Id.eq(todolist_id))
        .filter(todo_list::Column::UserId.eq(user_id))
        .exec(db)
        .await?;
    if result.rows_affected == 0 {
        return Err(AppError::not_found(format!(
            "未找到ID为 {todolist_id} 的备忘"
        )));
    }
    Ok(())
}

/// 删除本人备忘(先查询再判定归属; NULL 归属的存量数据允许删除)
///
/// :raises: AppError::not_found 备忘不存在或不属于当前用户
pub async fn delete(
    db: &DatabaseConnection,
    todolist_id: &str,
    user_id: &str,
) -> Result<(), AppError> {
    let existing = todo_list::Entity::find_by_id(todolist_id.to_owned())
        .one(db)
        .await?;
    let deletable = existing
        .as_ref()
        .map(|t| t.user_id.as_ref().map(|uid| uid == user_id).unwrap_or(true))
        .unwrap_or(false);
    if !deletable {
        return Err(AppError::not_found(format!(
            "未找到ID为 {todolist_id} 的备忘"
        )));
    }
    todo_list::Entity::delete_by_id(todolist_id.to_owned())
        .exec(db)
        .await?;
    Ok(())
}

/// 本人备忘列表查询(标题模糊/状态过滤, 列表与计数共用)
fn mine_select(user_id: &str, name: Option<&str>, status: Option<&str>) -> Select<todo_list::Entity> {
    let mut select = todo_list::Entity::find().filter(todo_list::Column::UserId.eq(user_id));
    if let Some(n) = name {
        select = select.filter(todo_list::Column::Name.contains(n));
    }
    if let Some(s) = status {
        select = select.filter(todo_list::Column::Status.eq(s));
    }
    select
}

/// 分页查询本人备忘列表(按备忘时间倒序)
pub async fn list_mine(
    db: &DatabaseConnection,
    pagination: &PaginationParams,
    user_id: &str,
    name: Option<&str>,
    status: Option<&str>,
) -> Result<Vec<todo_list::Model>, AppError> {
    Ok(mine_select(user_id, name, status)
        .order_by_desc(todo_list::Column::StartAt)
        .offset(pagination.offset())
        .limit(pagination.limit())
        .all(db)
        .await?)
}

/// 统计本人备忘总数(与列表过滤条件一致)
pub async fn count_mine(
    db: &DatabaseConnection,
    user_id: &str,
    name: Option<&str>,
    status: Option<&str>,
) -> Result<i64, AppError> {
    let total = mine_select(user_id, name, status).count(db).await?;
    Ok(total as i64)
}

/// 按时间范围查询本人备忘(日历 年/月/周 视图数据源, 按备忘时间升序)
pub async fn list_in_range(
    db: &DatabaseConnection,
    user_id: &str,
    start: DateTime<FixedOffset>,
    end: DateTime<FixedOffset>,
) -> Result<Vec<todo_list::Model>, AppError> {
    Ok(todo_list::Entity::find()
        .filter(todo_list::Column::UserId.eq(user_id))
        .filter(todo_list::Column::StartAt.gte(start))
        .filter(todo_list::Column::StartAt.lt(end))
        .order_by_asc(todo_list::Column::StartAt)
        .all(db)
        .await?)
}
