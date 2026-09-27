//! 字典项数据访问(对齐 Python module_main/dao/dict_item.py)

use sea_orm::{
    ActiveModelTrait, ColumnTrait, DatabaseConnection, EntityTrait, PaginatorTrait, QueryFilter,
    QueryOrder, QuerySelect, Set,
};

use common::utils::error::AppError;
use common::utils::pagination::{InfiniteScrollParams, PaginationParams, ScrollDirection};
use crate::do_::entity::{dict_item, dict_type};

use crate::do_::dict_item::{DictItemCreate, DictItemUpdate};

/// DbErr 中"记录不存在"→ 404(其余原样转 500)
fn map_not_found(e: sea_orm::DbErr, id: &str, name: &str) -> AppError {
    match e {
        sea_orm::DbErr::RecordNotFound(_) => AppError::not_found(format!("未找到ID为 {id} 的{name}")),
        other => other.into(),
    }
}

/// 新增字典项(返回新ID)
pub async fn add(db: &DatabaseConnection, data: DictItemCreate) -> Result<String, AppError> {
    let now = chrono::Utc::now().fixed_offset();
    let model = dict_item::ActiveModel {
        id: Set(uuid::Uuid::new_v4().simple().to_string()),
        dict_type_id: Set(data.dict_type_id),
        item_code: Set(data.item_code),
        item_name: Set(data.item_name),
        item_value: Set(data.item_value),
        description: Set(data.description),
        is_active: Set(data.is_active),
        sort_order: Set(data.sort_order),
        created_at: Set(Some(now)),
        updated_at: Set(now),
    }
    .insert(db)
    .await?;
    Ok(model.id)
}

/// 按ID删除字典项(不存在 404)
pub async fn delete(db: &DatabaseConnection, id: &str) -> Result<(), AppError> {
    let res = dict_item::Entity::delete_by_id(id).exec(db).await?;
    if res.rows_affected == 0 {
        return Err(AppError::not_found(format!("未找到ID为 {id} 的字典项")));
    }
    Ok(())
}

/// 按ID部分更新字典项(仅显式传入的字段生效; 不存在 404)
pub async fn update(db: &DatabaseConnection, id: &str, data: DictItemUpdate) -> Result<(), AppError> {
    let mut am = dict_item::ActiveModel { id: Set(id.to_string()), ..Default::default() };
    am.dict_type_id = Set(data.dict_type_id);
    am.item_code = Set(data.item_code);
    am.item_name = Set(data.item_name);
    match data.item_value {
        Some(Some(v)) => am.item_value = Set(Some(v)),
        Some(None) => am.item_value = Set(None),
        None => {}
    }
    match data.description {
        Some(Some(v)) => am.description = Set(Some(v)),
        Some(None) => am.description = Set(None),
        None => {}
    }
    if let Some(v) = data.is_active {
        am.is_active = Set(v);
    }
    if let Some(v) = data.sort_order {
        am.sort_order = Set(v);
    }
    // 对齐 SQLModel onupdate: 任何更新都刷新 updated_at
    am.updated_at = Set(chrono::Utc::now().fixed_offset());
    am.update(db).await.map_err(|e| map_not_found(e, id, "字典项"))?;
    Ok(())
}

/// 查询单个字典项
pub async fn get(db: &DatabaseConnection, id: &str) -> Option<dict_item::Model> {
    dict_item::Entity::find_by_id(id).one(db).await.ok().flatten()
}

/// 根据字典项编码全局查询(不限类型)
pub async fn get_by_code(db: &DatabaseConnection, item_code: &str) -> Option<dict_item::Model> {
    dict_item::Entity::find()
        .filter(dict_item::Column::ItemCode.eq(item_code))
        .one(db)
        .await
        .ok()
        .flatten()
}

/// 根据字典类型编码查询全部字典项(按 sort_order 排序; 类型不存在返回空列表)
pub async fn list_by_dict_type(
    db: &DatabaseConnection,
    type_code: &str,
) -> Result<Vec<dict_item::Model>, AppError> {
    // 先按编码查类型(拿到类型ID), 再按类型ID查字典项列表
    let Some(dict_type) = dict_type::Entity::find()
        .filter(dict_type::Column::TypeCode.eq(type_code))
        .one(db)
        .await?
    else {
        return Ok(Vec::new());
    };
    let items = dict_item::Entity::find()
        .filter(dict_item::Column::DictTypeId.eq(dict_type.id))
        .order_by_asc(dict_item::Column::SortOrder)
        .all(db)
        .await?;
    Ok(items)
}

/// 分页取字典项列表项(无过滤)
pub async fn list_paged_items(
    db: &DatabaseConnection,
    pagination: &PaginationParams,
) -> Result<Vec<dict_item::Model>, AppError> {
    Ok(dict_item::Entity::find()
        .offset(pagination.offset())
        .limit(pagination.limit())
        .all(db)
        .await?)
}

/// 统计字典项总数(全表)
pub async fn count(db: &DatabaseConnection) -> Result<i64, AppError> {
    Ok(dict_item::Entity::find().count(db).await? as i64)
}

/// 根据字典类型编码统计字典项数量(先按编码查类型, 类型不存在返回 0)
pub async fn count_by_dict_type(
    db: &DatabaseConnection,
    type_code: &str,
) -> Result<i64, AppError> {
    let Some(dict_type) = dict_type::Entity::find()
        .filter(dict_type::Column::TypeCode.eq(type_code))
        .one(db)
        .await?
    else {
        return Ok(0);
    };
    let count = dict_item::Entity::find()
        .filter(dict_item::Column::DictTypeId.eq(dict_type.id))
        .count(db)
        .await? as i64;
    Ok(count)
}

/// 滚动排序字段白名单(非法字段 → 500, 对齐 Python getattr AttributeError 行为)
fn sort_column(sort_by: &str) -> Result<dict_item::Column, AppError> {
    Ok(match sort_by {
        "created_at" => dict_item::Column::CreatedAt,
        "updated_at" => dict_item::Column::UpdatedAt,
        "sort_order" => dict_item::Column::SortOrder,
        "item_code" => dict_item::Column::ItemCode,
        "item_name" => dict_item::Column::ItemName,
        other => return Err(AppError::Internal(format!("未知排序字段: {other}"))),
    })
}

/// 游标记录的排序字段值(空值不参与过滤)
fn cursor_value(model: &dict_item::Model, col: dict_item::Column) -> Option<sea_orm::sea_query::Value> {
    match col {
        dict_item::Column::CreatedAt => model.created_at.map(|v| v.into()),
        dict_item::Column::UpdatedAt => Some(model.updated_at.into()),
        dict_item::Column::SortOrder => Some(model.sort_order.into()),
        dict_item::Column::ItemCode => Some(model.item_code.clone().into()),
        dict_item::Column::ItemName => Some(model.item_name.clone().into()),
        _ => None,
    }
}

/// 无限滚动取数据项(UP: 取更新更晚更大的数据; limit+1 探测 has_more; 响应组装在 services 层)
pub async fn scroll_items(
    db: &DatabaseConnection,
    params: &InfiniteScrollParams,
) -> Result<Vec<dict_item::Model>, AppError> {
    let col = sort_column(&params.sort_by)?;
    let up = params.direction == ScrollDirection::Up;
    let mut query = dict_item::Entity::find();
    if let Some(last_id) = params.last_id.as_deref().filter(|s| !s.is_empty()) {
        let last = dict_item::Entity::find_by_id(last_id)
            .one(db)
            .await?
            .ok_or_else(|| AppError::not_found(format!("未找到ID为 {last_id} 的字典项")))?;
        if let Some(value) = cursor_value(&last, col) {
            // UP: col > 游标值; DOWN: col < 游标值
            query = query.filter(if up { col.gt(value) } else { col.lt(value) });
        }
    }
    let items = query
        .order_by(col, if up { sea_orm::Order::Asc } else { sea_orm::Order::Desc })
        .limit((params.limit + 1).max(0) as u64)
        .all(db)
        .await?;
    Ok(items)
}
