//! 角色数据访问(对齐 Python dao/role.py)
//!
//! 仅做数据库读写; 内置角色声明的变更判定与运行期 CRUD 规则在 services 层。

use sea_orm::{ActiveModelTrait, ColumnTrait, DatabaseConnection, EntityTrait, PaginatorTrait, QueryFilter, QueryOrder, QuerySelect, Select, Set};
use uuid::Uuid;

use crate::do_::entity::role;

use common::utils::error::AppError;

use crate::do_::now_utc;
use crate::do_::role::{RoleCreate, RoleUpdate};

/// 按角色 key 查询
pub async fn find_by_key(
    db: &DatabaseConnection,
    role_key: &str,
) -> Result<Option<role::Model>, AppError> {
    Ok(role::Entity::find()
        .filter(role::Column::RoleKey.eq(role_key))
        .one(db)
        .await?)
}

/// 按角色名称精确查询
pub async fn find_by_name(
    db: &DatabaseConnection,
    name: &str,
) -> Result<Option<role::Model>, AppError> {
    Ok(role::Entity::find()
        .filter(role::Column::Name.eq(name))
        .one(db)
        .await?)
}

/// 按ID查询角色
pub async fn get(db: &DatabaseConnection, role_id: &str) -> Result<Option<role::Model>, AppError> {
    Ok(role::Entity::find_by_id(role_id).one(db).await?)
}

/// 插入角色记录(字段缺省值与 Python Role 模型一致: sort=0, data_scope="1", is_active=true)
pub async fn insert(db: &DatabaseConnection, data: RoleCreate) -> Result<role::Model, AppError> {
    let now = now_utc();
    let am = role::ActiveModel {
        name: Set(data.name),
        role_key: Set(data.role_key),
        description: Set(data.description),
        sort: Set(data.sort.unwrap_or(0)),
        data_scope: Set(data.data_scope.unwrap_or_else(|| "1".to_string())),
        is_active: Set(data.is_active.unwrap_or(true)),
        id: Set(Uuid::new_v4().simple().to_string()),
        created_at: Set(Some(now)),
        updated_at: Set(now),
    };
    Ok(am.insert(db).await?)
}

/// 部分更新角色记录(仅显式传入字段生效, 并刷新 updated_at)
pub async fn update(
    db: &DatabaseConnection,
    model: role::Model,
    data: RoleUpdate,
) -> Result<role::Model, AppError> {
    let mut am: role::ActiveModel = model.into();
    if let Some(v) = data.name {
        am.name = Set(v);
    }
    if let Some(v) = data.role_key {
        am.role_key = Set(v);
    }
    if let Some(v) = data.description {
        am.description = Set(Some(v));
    }
    if let Some(v) = data.sort {
        am.sort = Set(v);
    }
    if let Some(v) = data.data_scope {
        am.data_scope = Set(v);
    }
    if let Some(v) = data.is_active {
        am.is_active = Set(v);
    }
    am.updated_at = Set(now_utc());
    Ok(am.update(db).await?)
}

/// 删除角色记录(返回是否实际删除)
pub async fn delete(db: &DatabaseConnection, role_id: &str) -> Result<bool, AppError> {
    let result = role::Entity::delete_by_id(role_id).exec(db).await?;
    Ok(result.rows_affected > 0)
}

/// 角色列表查询构建(名称/权限字符模糊, 状态精确; 列表与计数共用)
fn role_select(
    name: Option<&str>,
    role_key: Option<&str>,
    is_active: Option<bool>,
) -> Select<role::Entity> {
    let mut select = role::Entity::find();
    if let Some(kw) = name {
        select = select.filter(role::Column::Name.contains(kw));
    }
    if let Some(kw) = role_key {
        select = select.filter(role::Column::RoleKey.contains(kw));
    }
    if let Some(active) = is_active {
        select = select.filter(role::Column::IsActive.eq(active));
    }
    select
}

/// 分页查询角色列表(与 Python 一致无排序; 返回 (当前页数据, 总数))
pub async fn list_paged(
    db: &DatabaseConnection,
    offset: u64,
    limit: u64,
    name: Option<&str>,
    role_key: Option<&str>,
    is_active: Option<bool>,
) -> Result<(Vec<role::Model>, u64), AppError> {
    let select = role_select(name, role_key, is_active);
    let total = select.clone().count(db).await?;
    let items = select.offset(offset).limit(limit).all(db).await?;
    Ok((items, total))
}

/// 全部角色(不分页, 按 sort 升序, 用于下拉选择)
pub async fn list_all(db: &DatabaseConnection) -> Result<Vec<role::Model>, AppError> {
    Ok(role::Entity::find()
        .order_by_asc(role::Column::Sort)
        .all(db)
        .await?)
}
