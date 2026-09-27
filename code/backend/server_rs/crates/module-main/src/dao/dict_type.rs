//! 字典类型数据访问(对齐 Python module_main/dao/dict_type.py)

use sea_orm::{
    ActiveModelTrait, ColumnTrait, Condition, DatabaseConnection, EntityTrait, PaginatorTrait,
    QueryFilter, QueryOrder, QuerySelect, Select, Set,
};

use common::utils::error::AppError;
use common::utils::pagination::{InfiniteScrollParams, PaginationParams, ScrollDirection};
use crate::do_::entity::dict_type;

use crate::do_::dict_type::{DictTypeCreate, DictTypeUpdate};

/// DbErr 中"记录不存在"→ 404(其余原样转 500)
fn map_not_found(e: sea_orm::DbErr, id: &str, name: &str) -> AppError {
    match e {
        sea_orm::DbErr::RecordNotFound(_) => AppError::not_found(format!("未找到ID为 {id} 的{name}")),
        other => other.into(),
    }
}

/// 新增字典类型(返回新ID; id/created_at/updated_at 由本侧生成, 对齐模型 default_factory)
pub async fn add(db: &DatabaseConnection, data: DictTypeCreate) -> Result<String, AppError> {
    let now = chrono::Utc::now().fixed_offset();
    let model = dict_type::ActiveModel {
        id: Set(uuid::Uuid::new_v4().simple().to_string()),
        type_code: Set(data.type_code),
        type_name: Set(data.type_name),
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

/// 按ID删除字典类型(仅删除类型本身, 不级联删除其下字典项; 不存在 404)
pub async fn delete(db: &DatabaseConnection, id: &str) -> Result<(), AppError> {
    let res = dict_type::Entity::delete_by_id(id).exec(db).await?;
    if res.rows_affected == 0 {
        return Err(AppError::not_found(format!("未找到ID为 {id} 的字典类型")));
    }
    Ok(())
}

/// 按ID部分更新字典类型(仅请求体中显式传入的字段生效; 不存在 404)
pub async fn update(db: &DatabaseConnection, id: &str, data: DictTypeUpdate) -> Result<(), AppError> {
    let mut am = dict_type::ActiveModel { id: Set(id.to_string()), ..Default::default() };
    am.type_code = Set(data.type_code);
    am.type_name = Set(data.type_name);
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
    am.update(db).await.map_err(|e| map_not_found(e, id, "字典类型"))?;
    Ok(())
}

/// 查询单个字典类型
pub async fn get(db: &DatabaseConnection, id: &str) -> Option<dict_type::Model> {
    dict_type::Entity::find_by_id(id).one(db).await.ok().flatten()
}

/// 根据字典类型编码查询
pub async fn get_by_code(db: &DatabaseConnection, type_code: &str) -> Option<dict_type::Model> {
    dict_type::Entity::find()
        .filter(dict_type::Column::TypeCode.eq(type_code))
        .one(db)
        .await
        .ok()
        .flatten()
}

/// 列表查询构建(类型名称/编码模糊 + 状态精确, 列表与计数共用)
fn select(keyword: Option<&str>, is_active: Option<bool>) -> Select<dict_type::Entity> {
    let mut query = dict_type::Entity::find();
    if let Some(kw) = keyword.filter(|k| !k.is_empty()) {
        query = query.filter(
            Condition::any()
                .add(dict_type::Column::TypeName.contains(kw))
                .add(dict_type::Column::TypeCode.contains(kw)),
        );
    }
    if let Some(active) = is_active {
        query = query.filter(dict_type::Column::IsActive.eq(active));
    }
    query
}

/// 分页取字典类型列表项(与 Python 一致不排序)
pub async fn list_paged_items(
    db: &DatabaseConnection,
    pagination: &PaginationParams,
    keyword: Option<&str>,
    is_active: Option<bool>,
) -> Result<Vec<dict_type::Model>, AppError> {
    Ok(select(keyword, is_active)
        .offset(pagination.offset())
        .limit(pagination.limit())
        .all(db)
        .await?)
}

/// 统计字典类型总数(与列表过滤条件一致)
pub async fn count(
    db: &DatabaseConnection,
    keyword: Option<&str>,
    is_active: Option<bool>,
) -> Result<i64, AppError> {
    Ok(select(keyword, is_active).count(db).await? as i64)
}

/// 滚动排序字段白名单(非法字段 → 500, 对齐 Python getattr AttributeError 行为)
fn sort_column(sort_by: &str) -> Result<dict_type::Column, AppError> {
    Ok(match sort_by {
        "created_at" => dict_type::Column::CreatedAt,
        "updated_at" => dict_type::Column::UpdatedAt,
        "sort_order" => dict_type::Column::SortOrder,
        "type_code" => dict_type::Column::TypeCode,
        "type_name" => dict_type::Column::TypeName,
        other => return Err(AppError::Internal(format!("未知排序字段: {other}"))),
    })
}

/// 游标记录的排序字段值(空值不参与过滤)
fn cursor_value(model: &dict_type::Model, col: dict_type::Column) -> Option<sea_orm::sea_query::Value> {
    match col {
        dict_type::Column::CreatedAt => model.created_at.map(|v| v.into()),
        dict_type::Column::UpdatedAt => Some(model.updated_at.into()),
        dict_type::Column::SortOrder => Some(model.sort_order.into()),
        dict_type::Column::TypeCode => Some(model.type_code.clone().into()),
        dict_type::Column::TypeName => Some(model.type_name.clone().into()),
        _ => None,
    }
}

/// 无限滚动取数据项(UP: 取更新更晚更大的数据; limit+1 探测 has_more; 响应组装在 services 层)
pub async fn scroll_items(
    db: &DatabaseConnection,
    params: &InfiniteScrollParams,
) -> Result<Vec<dict_type::Model>, AppError> {
    let col = sort_column(&params.sort_by)?;
    let up = params.direction == ScrollDirection::Up;
    let mut query = dict_type::Entity::find();
    if let Some(last_id) = params.last_id.as_deref().filter(|s| !s.is_empty()) {
        let last = dict_type::Entity::find_by_id(last_id)
            .one(db)
            .await?
            .ok_or_else(|| AppError::not_found(format!("未找到ID为 {last_id} 的字典类型")))?;
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
