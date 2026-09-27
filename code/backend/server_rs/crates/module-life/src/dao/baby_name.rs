//! 宝宝名字数据访问(对齐 Python module_life/dao/baby_name.py)
//!
//! 只做数据库读写: 名字记录 CRUD + 滚动查询 + 模型配置存在性探测;
//! 名字长度校验/回退链等业务规则在 services 层。

use sea_orm::sea_query::Expr;
use sea_orm::{
    ActiveModelTrait, ColumnTrait, DatabaseConnection, EntityTrait, PaginatorTrait, QueryFilter,
    QueryOrder, QuerySelect, Select, Set,
};
use uuid::Uuid;

use crate::do_::entity::baby_name;
use module_ai::do_::entity::model_config;

use common::utils::error::AppError;
use common::utils::pagination::{InfiniteScrollParams, PaginationParams, ScrollDirection};

use crate::do_::baby_name::{BabyNameCreate, BabyNameUpdate};
use crate::do_::now_utc;

/// 新增宝宝名字记录
///
/// :param data: 名字创建数据(未传字段取 Python 模型默认值)
/// :return: 新创建名字ID
pub async fn add(db: &DatabaseConnection, data: BabyNameCreate) -> Result<String, AppError> {
    let id = Uuid::new_v4().simple().to_string();
    let am = baby_name::ActiveModel {
        name: Set(data.name),
        gender: Set(data.gender.to_entity()),
        style: Set(data.style.to_entity()),
        meaning: Set(data.meaning),
        pinyin: Set(data.pinyin),
        stroke_count: Set(data.stroke_count),
        // 未传字段取 Python 模型默认值(实体列可空, 统一以 Some 包装)
        is_lucky: Set(Some(data.is_lucky.unwrap_or(true))),
        popularity: Set(data.popularity.unwrap_or(0)),
        tags: Set(data.tags),
        source: Set(data.source),
        is_active: Set(Some(data.is_active.unwrap_or(true))),
        id: Set(id.clone()),
        created_at: Set(Some(now_utc())),
        updated_at: Set(now_utc()),
    };
    am.insert(db).await?;
    Ok(id)
}

/// 查询单个宝宝名字记录
pub async fn get(
    db: &DatabaseConnection,
    name_id: &str,
) -> Result<Option<baby_name::Model>, AppError> {
    Ok(baby_name::Entity::find_by_id(name_id.to_owned())
        .one(db)
        .await?)
}

/// 直接更新宝宝名字记录(不先查询, 仅显式传入的字段生效)
///
/// :raises: AppError::not_found 名字不存在
pub async fn update(
    db: &DatabaseConnection,
    name_id: &str,
    data: BabyNameUpdate,
) -> Result<(), AppError> {
    // 三态更新: 未传不更新 / 传 null 置 NULL / 传值更新; 显式刷新 updated_at
    let mut update =
        baby_name::Entity::update_many().col_expr(baby_name::Column::UpdatedAt, Expr::value(now_utc()));
    if let Some(v) = data.name {
        update = update.col_expr(baby_name::Column::Name, Expr::value(v));
    }
    if let Some(v) = data.gender {
        update = update.col_expr(
            baby_name::Column::Gender,
            Expr::value(v.db_value().to_string()),
        );
    }
    if let Some(v) = data.style {
        update = update.col_expr(
            baby_name::Column::Style,
            Expr::value(v.db_value().to_string()),
        );
    }
    if let Some(v) = data.meaning {
        update = update.col_expr(baby_name::Column::Meaning, Expr::value(v));
    }
    if let Some(v) = data.pinyin {
        update = update.col_expr(baby_name::Column::Pinyin, Expr::value(v));
    }
    if let Some(v) = data.stroke_count {
        update = update.col_expr(baby_name::Column::StrokeCount, Expr::value(v));
    }
    if let Some(v) = data.is_lucky {
        update = update.col_expr(baby_name::Column::IsLucky, Expr::value(v));
    }
    if let Some(v) = data.popularity {
        update = update.col_expr(baby_name::Column::Popularity, Expr::value(v));
    }
    if let Some(v) = data.tags {
        update = update.col_expr(baby_name::Column::Tags, Expr::value(v));
    }
    if let Some(v) = data.source {
        update = update.col_expr(baby_name::Column::Source, Expr::value(v));
    }
    if let Some(v) = data.is_active {
        update = update.col_expr(baby_name::Column::IsActive, Expr::value(v));
    }
    let result = update
        .filter(baby_name::Column::Id.eq(name_id))
        .exec(db)
        .await?;
    if result.rows_affected == 0 {
        return Err(AppError::not_found(format!(
            "未找到ID为 {name_id} 的宝宝名字"
        )));
    }
    Ok(())
}

/// 删除宝宝名字记录(与 Python 一致: 先查后删)
///
/// :raises: AppError::not_found 名字不存在
pub async fn delete(db: &DatabaseConnection, name_id: &str) -> Result<(), AppError> {
    let existing = baby_name::Entity::find_by_id(name_id.to_owned())
        .one(db)
        .await?;
    if existing.is_none() {
        return Err(AppError::not_found(format!(
            "未找到ID为 {name_id} 的宝宝名字"
        )));
    }
    baby_name::Entity::delete_by_id(name_id.to_owned())
        .exec(db)
        .await?;
    Ok(())
}

/// 批量删除宝宝名字记录
///
/// :return: 实际删除条数
pub async fn batch_delete(db: &DatabaseConnection, ids: Vec<String>) -> Result<i64, AppError> {
    if ids.is_empty() {
        return Ok(0);
    }
    let result = baby_name::Entity::delete_many()
        .filter(baby_name::Column::Id.is_in(ids))
        .exec(db)
        .await?;
    Ok(result.rows_affected as i64)
}

/// 基础查询(列表与计数共用, 无过滤条件)
fn base_select() -> Select<baby_name::Entity> {
    baby_name::Entity::find()
}

/// 分页查询宝宝名字列表(无排序, 与 Python list_paged 一致)
pub async fn list_paged(
    db: &DatabaseConnection,
    pagination: &PaginationParams,
) -> Result<Vec<baby_name::Model>, AppError> {
    Ok(base_select()
        .offset(pagination.offset())
        .limit(pagination.limit())
        .all(db)
        .await?)
}

/// 统计宝宝名字总数
pub async fn count(db: &DatabaseConnection) -> Result<i64, AppError> {
    let total = base_select().count(db).await?;
    Ok(total as i64)
}

/// 滚动排序字段白名单(Python 用 getattr 动态取列, 非法字段 500; 此处收敛为 400)
fn scroll_column(sort_by: &str) -> Result<baby_name::Column, AppError> {
    Ok(match sort_by {
        "" | "created_at" => baby_name::Column::CreatedAt,
        "id" => baby_name::Column::Id,
        "name" => baby_name::Column::Name,
        "popularity" => baby_name::Column::Popularity,
        "updated_at" => baby_name::Column::UpdatedAt,
        other => {
            return Err(AppError::business(format!("不支持的排序字段: {other}")));
        }
    })
}

/// 无限滚动加载宝宝名字列表(last_id 游标 + 排序字段, 查 limit+1 条供 has_more 判断)
///
/// :raises: AppError::not_found 游标锚点记录不存在
pub async fn scroll(
    db: &DatabaseConnection,
    params: &InfiniteScrollParams,
) -> Result<Vec<baby_name::Model>, AppError> {
    let column = scroll_column(&params.sort_by)?;
    let mut select = base_select();
    if let Some(last_id) = &params.last_id {
        // 游标锚点校验(不存在 404)
        let anchor = baby_name::Entity::find_by_id(last_id.to_owned())
            .one(db)
            .await?
            .ok_or_else(|| AppError::not_found(format!("未找到ID为 {last_id} 的宝宝名字")))?;
        // UP 升序取更新数据 / DOWN 降序
        select = match (column, params.direction) {
            (baby_name::Column::Id, ScrollDirection::Up) => {
                select.filter(baby_name::Column::Id.gt(anchor.id.clone()))
            }
            (baby_name::Column::Id, ScrollDirection::Down) => {
                select.filter(baby_name::Column::Id.lt(anchor.id.clone()))
            }
            (baby_name::Column::Name, ScrollDirection::Up) => {
                select.filter(baby_name::Column::Name.gt(anchor.name.clone()))
            }
            (baby_name::Column::Name, ScrollDirection::Down) => {
                select.filter(baby_name::Column::Name.lt(anchor.name.clone()))
            }
            (baby_name::Column::Popularity, ScrollDirection::Up) => {
                select.filter(baby_name::Column::Popularity.gt(anchor.popularity))
            }
            (baby_name::Column::Popularity, ScrollDirection::Down) => {
                select.filter(baby_name::Column::Popularity.lt(anchor.popularity))
            }
            (baby_name::Column::UpdatedAt, ScrollDirection::Up) => {
                select.filter(baby_name::Column::UpdatedAt.gt(anchor.updated_at))
            }
            (baby_name::Column::UpdatedAt, ScrollDirection::Down) => {
                select.filter(baby_name::Column::UpdatedAt.lt(anchor.updated_at))
            }
            (baby_name::Column::CreatedAt, ScrollDirection::Up) => {
                select.filter(baby_name::Column::CreatedAt.gt(anchor.created_at))
            }
            _ => select.filter(baby_name::Column::CreatedAt.lt(anchor.created_at)),
        };
    }
    // 正反排序(查 limit+1 条供 has_more 判断)
    let query = if params.direction == ScrollDirection::Up {
        select.order_by_asc(column)
    } else {
        select.order_by_desc(column)
    };
    Ok(query
        .limit((params.limit.max(0) + 1) as u64)
        .all(db)
        .await?)
}

/// 判断指定模型配置是否存在
pub async fn model_exists(db: &DatabaseConnection, model_id: &str) -> Result<bool, AppError> {
    Ok(model_config::Entity::find_by_id(model_id.to_owned())
        .one(db)
        .await?
        .is_some())
}

/// 判断默认公共 chat 模型(public + is_default + is_active)是否存在
pub async fn default_chat_model_exists(db: &DatabaseConnection) -> Result<bool, AppError> {
    Ok(model_config::Entity::find()
        .filter(model_config::Column::ModelType.eq("chat"))
        .filter(model_config::Column::Scope.eq("public"))
        .filter(model_config::Column::IsDefault.eq(true))
        .filter(model_config::Column::IsActive.eq(true))
        .one(db)
        .await?
        .is_some())
}
