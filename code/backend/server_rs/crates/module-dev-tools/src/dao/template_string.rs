//! 模板字符串数据访问(对齐 Python module_dev_tools/dao/template_string.py)

use sea_orm::sea_query::Expr;
use sea_orm::{
    ActiveModelTrait, ColumnTrait, DatabaseConnection, EntityTrait, PaginatorTrait, QueryFilter,
    QueryOrder, QuerySelect, Select, Set,
};
use uuid::Uuid;

use crate::do_::entity::template_string;

use common::utils::error::AppError;
use common::utils::pagination::{InfiniteScrollParams, PaginationParams, ScrollDirection};

use crate::do_::now_utc;
use crate::do_::template_string::{TemplateStringCreate, TemplateStringUpdate};

/// 新增模板字符串记录(tags 由服务层解析后传入, 未传 is_active 取默认 true)
///
/// :return: 新创建记录ID
pub async fn add(
    db: &DatabaseConnection,
    data: TemplateStringCreate,
    tags: serde_json::Value,
) -> Result<String, AppError> {
    let id = Uuid::new_v4().simple().to_string();
    let am = template_string::ActiveModel {
        id: Set(id.clone()),
        name: Set(data.name),
        description: Set(data.description),
        template_content: Set(data.template_content),
        category: Set(data.category),
        tags: Set(Some(tags)),
        is_active: Set(data.is_active.unwrap_or(true)),
        created_at: Set(Some(now_utc())),
        updated_at: Set(now_utc()),
    };
    am.insert(db).await?;
    Ok(id)
}

/// 查询单条模板字符串
pub async fn get(
    db: &DatabaseConnection,
    template_string_id: &str,
) -> Result<Option<template_string::Model>, AppError> {
    Ok(template_string::Entity::find_by_id(template_string_id.to_owned())
        .one(db)
        .await?)
}

/// 删除模板字符串
///
/// :raises: AppError::not_found 记录不存在
pub async fn delete(db: &DatabaseConnection, template_string_id: &str) -> Result<(), AppError> {
    let result = template_string::Entity::delete_many()
        .filter(template_string::Column::Id.eq(template_string_id))
        .exec(db)
        .await?;
    if result.rows_affected == 0 {
        return Err(AppError::not_found(format!(
            "未找到ID为 {template_string_id} 的模板字符串"
        )));
    }
    Ok(())
}

/// 直接更新模板字符串记录(不先查询, 仅显式传入字段生效;
/// tags 三态转 JSON 数组, updated_at 显式刷新对应 Python onupdate 语义)
///
/// :raises: AppError::not_found 记录不存在
pub async fn update(
    db: &DatabaseConnection,
    template_string_id: &str,
    data: TemplateStringUpdate,
) -> Result<(), AppError> {
    let mut update = template_string::Entity::update_many()
        .col_expr(template_string::Column::UpdatedAt, Expr::value(now_utc()));
    if let Some(v) = data.name {
        update = update.col_expr(template_string::Column::Name, Expr::value(v));
    }
    if let Some(v) = data.description {
        update = update.col_expr(template_string::Column::Description, Expr::value(v));
    }
    if let Some(v) = data.template_content {
        update = update.col_expr(template_string::Column::TemplateContent, Expr::value(v));
    }
    if let Some(v) = data.category {
        update = update.col_expr(template_string::Column::Category, Expr::value(v));
    }
    if let Some(v) = data.tags {
        // Vec<String> → JSON 数组; 显式 null 置 NULL
        let value: Option<serde_json::Value> = v
            .map(|list| {
                serde_json::Value::Array(
                    list.into_iter().map(serde_json::Value::String).collect(),
                )
            });
        update = update.col_expr(template_string::Column::Tags, Expr::value(value));
    }
    if let Some(v) = data.is_active {
        update = update.col_expr(template_string::Column::IsActive, Expr::value(v));
    }
    let result = update
        .filter(template_string::Column::Id.eq(template_string_id))
        .exec(db)
        .await?;
    if result.rows_affected == 0 {
        return Err(AppError::not_found(format!(
            "未找到ID为 {template_string_id} 的模板字符串"
        )));
    }
    Ok(())
}

/// 无限滚动查询模板字符串(游标记录不存在 404; limit+1 探测 has_more)
pub async fn scroll(
    db: &DatabaseConnection,
    params: &InfiniteScrollParams,
) -> Result<Vec<template_string::Model>, AppError> {
    let col = sort_column(&params.sort_by)?;
    let mut select = template_string::Entity::find();
    if let Some(last_id) = &params.last_id {
        let last = template_string::Entity::find_by_id(last_id)
            .one(db)
            .await?
            .ok_or_else(|| {
                AppError::not_found(format!("未找到ID为 {last_id} 的模板字符串"))
            })?;
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

/// 全表查询构建(列表与计数共用, 不做条件过滤)
fn base_select() -> Select<template_string::Entity> {
    template_string::Entity::find()
}

/// 统计模板字符串总数
pub async fn count_all(db: &DatabaseConnection) -> Result<i64, AppError> {
    let total = base_select().count(db).await?;
    Ok(total as i64)
}

/// 分页查询模板字符串列表(不做条件过滤)
pub async fn list_paged(
    db: &DatabaseConnection,
    pagination: &PaginationParams,
) -> Result<Vec<template_string::Model>, AppError> {
    Ok(base_select()
        .offset(pagination.offset())
        .limit(pagination.limit())
        .all(db)
        .await?)
}

/// 将排序字段名映射为列(未知字段报 500, 对齐 Python getattr 的 AttributeError 行为)
fn sort_column(sort_by: &str) -> Result<template_string::Column, AppError> {
    Ok(match sort_by {
        "name" => template_string::Column::Name,
        "description" => template_string::Column::Description,
        "template_content" => template_string::Column::TemplateContent,
        "category" => template_string::Column::Category,
        "tags" => template_string::Column::Tags,
        "is_active" => template_string::Column::IsActive,
        "id" => template_string::Column::Id,
        "created_at" => template_string::Column::CreatedAt,
        "updated_at" => template_string::Column::UpdatedAt,
        _ => {
            return Err(AppError::Internal(format!(
                "无效的排序字段: {sort_by}"
            )))
        }
    })
}

/// 取排序字段在指定记录上的值(用于游标比较)
fn sort_value(col: template_string::Column, m: &template_string::Model) -> sea_orm::sea_query::Value {
    match col {
        template_string::Column::Name => m.name.clone().into(),
        template_string::Column::Description => m.description.clone().into(),
        template_string::Column::TemplateContent => m.template_content.clone().into(),
        template_string::Column::Category => m.category.clone().into(),
        template_string::Column::Tags => m.tags.clone().into(),
        template_string::Column::IsActive => m.is_active.into(),
        template_string::Column::Id => m.id.clone().into(),
        template_string::Column::CreatedAt => m.created_at.into(),
        template_string::Column::UpdatedAt => m.updated_at.into(),
    }
}
