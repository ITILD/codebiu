//! 模板数据访问(对齐 Python module_template/dao/template.py)

use sea_orm::sea_query::Expr;
use sea_orm::{
    ActiveModelTrait, ColumnTrait, DatabaseConnection, EntityTrait, PaginatorTrait, QueryFilter,
    QueryOrder, QuerySelect, Select, Set,
};
use uuid::Uuid;

use crate::do_::entity::template;

use common::utils::error::AppError;
use common::utils::pagination::{InfiniteScrollParams, PaginationParams, ScrollDirection};

use crate::do_::now_utc;
use crate::do_::template::{TemplateCreate, TemplateUpdate};

/// 新增模板记录(未传字段取 Python 模型默认值: value=0, is_active=true)
///
/// :return: 新创建模板ID
pub async fn add(db: &DatabaseConnection, data: TemplateCreate) -> Result<String, AppError> {
    let id = Uuid::new_v4().simple().to_string();
    let am = template::ActiveModel {
        id: Set(id.clone()),
        pid: Set(data.pid),
        value: Set(data.value.unwrap_or(0)),
        name: Set(data.name),
        description: Set(data.description),
        is_active: Set(Some(data.is_active.unwrap_or(true))),
        created_at: Set(Some(now_utc())),
        updated_at: Set(now_utc()),
    };
    am.insert(db).await?;
    Ok(id)
}

/// 查询单个模板
pub async fn get(
    db: &DatabaseConnection,
    template_id: &str,
) -> Result<Option<template::Model>, AppError> {
    Ok(template::Entity::find_by_id(template_id.to_owned())
        .one(db)
        .await?)
}

/// 删除模板
///
/// :raises: AppError::not_found 模板不存在
pub async fn delete(db: &DatabaseConnection, template_id: &str) -> Result<(), AppError> {
    let result = template::Entity::delete_many()
        .filter(template::Column::Id.eq(template_id))
        .exec(db)
        .await?;
    if result.rows_affected == 0 {
        return Err(AppError::not_found(format!(
            "未找到ID为 {template_id} 的模板"
        )));
    }
    Ok(())
}

/// 批量删除模板(不存在的ID静默跳过)
///
/// :return: 实际删除数量
pub async fn batch_delete(db: &DatabaseConnection, ids: Vec<String>) -> Result<u64, AppError> {
    let result = template::Entity::delete_many()
        .filter(template::Column::Id.is_in(ids))
        .exec(db)
        .await?;
    Ok(result.rows_affected)
}

/// 直接更新模板记录(不先查询, 仅显式传入字段生效;
/// updated_at 显式刷新对应 Python onupdate 语义)
///
/// :raises: AppError::not_found 模板不存在
pub async fn update(
    db: &DatabaseConnection,
    template_id: &str,
    data: TemplateUpdate,
) -> Result<(), AppError> {
    let mut update = template::Entity::update_many()
        .col_expr(template::Column::UpdatedAt, Expr::value(now_utc()));
    if let Some(v) = data.pid {
        update = update.col_expr(template::Column::Pid, Expr::value(v));
    }
    if let Some(v) = data.value {
        update = update.col_expr(template::Column::Value, Expr::value(v));
    }
    if let Some(v) = data.name {
        update = update.col_expr(template::Column::Name, Expr::value(v));
    }
    if let Some(v) = data.description {
        update = update.col_expr(template::Column::Description, Expr::value(v));
    }
    if let Some(v) = data.is_active {
        update = update.col_expr(template::Column::IsActive, Expr::value(v));
    }
    let result = update
        .filter(template::Column::Id.eq(template_id))
        .exec(db)
        .await?;
    if result.rows_affected == 0 {
        return Err(AppError::not_found(format!(
            "未找到ID为 {template_id} 的模板"
        )));
    }
    Ok(())
}

/// 无限滚动查询(先查最新, 滚下拉取更早数据; 默认按 created_at)
///
/// 游标记录不存在时 404; 实际查询 limit+1 条探测 has_more(截断在 services 层组装)。
pub async fn scroll(
    db: &DatabaseConnection,
    params: &InfiniteScrollParams,
) -> Result<Vec<template::Model>, AppError> {
    let col = sort_column(&params.sort_by)?;
    let mut select = template::Entity::find();
    // 有游标时: 取上一条记录的排序字段值作比较基准
    if let Some(last_id) = &params.last_id {
        let last = template::Entity::find_by_id(last_id)
            .one(db)
            .await?
            .ok_or_else(|| AppError::not_found(format!("未找到ID为 {last_id} 的模板")))?;
        let value = sort_value(col, &last);
        select = match params.direction {
            ScrollDirection::Up => select.filter(col.gt(value)),
            ScrollDirection::Down => select.filter(col.lt(value)),
        };
    }
    select = match params.direction {
        ScrollDirection::Up => select.order_by_asc(col),
        ScrollDirection::Down => select.order_by_desc(col),
    };
    let items = select
        .limit(params.limit.max(0) as u64 + 1)
        .all(db)
        .await?;
    Ok(items)
}

/// 全表查询构建(列表与计数共用, 不做任何条件过滤)
fn base_select() -> Select<template::Entity> {
    template::Entity::find()
}

/// 统计模板总数
pub async fn count_all(db: &DatabaseConnection) -> Result<i64, AppError> {
    let total = base_select().count(db).await?;
    Ok(total as i64)
}

/// 分页查询模板列表(不做任何条件过滤)
pub async fn list_paged(
    db: &DatabaseConnection,
    pagination: &PaginationParams,
) -> Result<Vec<template::Model>, AppError> {
    Ok(base_select()
        .offset(pagination.offset())
        .limit(pagination.limit())
        .all(db)
        .await?)
}

/// 将排序字段名映射为列(未知字段报 500, 对齐 Python getattr 的 AttributeError 行为)
fn sort_column(sort_by: &str) -> Result<template::Column, AppError> {
    Ok(match sort_by {
        "pid" => template::Column::Pid,
        "value" => template::Column::Value,
        "name" => template::Column::Name,
        "description" => template::Column::Description,
        "is_active" => template::Column::IsActive,
        "id" => template::Column::Id,
        "created_at" => template::Column::CreatedAt,
        "updated_at" => template::Column::UpdatedAt,
        _ => {
            return Err(AppError::Internal(format!(
                "无效的排序字段: {sort_by}"
            )))
        }
    })
}

/// 取排序字段在指定记录上的值(用于游标比较)
fn sort_value(col: template::Column, m: &template::Model) -> sea_orm::sea_query::Value {
    match col {
        template::Column::Pid => m.pid.clone().into(),
        template::Column::Value => m.value.into(),
        template::Column::Name => m.name.clone().into(),
        template::Column::Description => m.description.clone().into(),
        template::Column::IsActive => m.is_active.into(),
        template::Column::Id => m.id.clone().into(),
        template::Column::CreatedAt => m.created_at.into(),
        template::Column::UpdatedAt => m.updated_at.into(),
    }
}
