//! 权限数据访问(对齐 Python dao/permission.py)
//!
//! 仅做数据库读写; 内置权限声明的变更判定与权限树组装在 services 层。

use sea_orm::{ActiveModelTrait, ColumnTrait, DatabaseConnection, EntityTrait, PaginatorTrait, QueryFilter, QueryOrder, QuerySelect, Set};
use uuid::Uuid;

use crate::do_::entity::permission;

use common::utils::error::AppError;

use crate::do_::now_utc;
use crate::do_::permission::{PermissionCreate, PermissionUpdate};

/// 按权限代码精确查询
pub async fn find_by_code(
    db: &DatabaseConnection,
    code: &str,
) -> Result<Option<permission::Model>, AppError> {
    Ok(permission::Entity::find()
        .filter(permission::Column::Code.eq(code))
        .one(db)
        .await?)
}

/// 按ID查询权限
pub async fn get(
    db: &DatabaseConnection,
    permission_id: &str,
) -> Result<Option<permission::Model>, AppError> {
    Ok(permission::Entity::find_by_id(permission_id).one(db).await?)
}

/// 插入权限记录(字段缺省值与 Python Permission 模型一致: order_num=0, visible=true, is_active=true)
pub async fn insert(
    db: &DatabaseConnection,
    data: PermissionCreate,
) -> Result<permission::Model, AppError> {
    let now = now_utc();
    let am = permission::ActiveModel {
        parent_id: Set(data.parent_id),
        name: Set(data.name),
        code: Set(data.code),
        description: Set(data.description),
        menu_type: Set(data.menu_type),
        path: Set(data.path),
        component: Set(data.component),
        perms: Set(data.perms),
        icon: Set(data.icon),
        order_num: Set(data.order_num.unwrap_or(0)),
        visible: Set(data.visible.unwrap_or(true)),
        is_active: Set(data.is_active.unwrap_or(true)),
        id: Set(Uuid::new_v4().simple().to_string()),
        created_at: Set(Some(now)),
        updated_at: Set(now),
    };
    Ok(am.insert(db).await?)
}

/// 声明式更新权限行(内置权限 upsert 命中变更时使用: 显式覆盖声明字段, 刷新 updated_at)
pub async fn update_declaration(
    db: &DatabaseConnection,
    model: permission::Model,
    name: &str,
    menu_type: &str,
    description: Option<&str>,
    path: Option<&str>,
    icon: Option<&str>,
    order_num: i32,
    visible: bool,
    parent_id: &str,
) -> Result<(), AppError> {
    let mut am: permission::ActiveModel = model.into();
    am.name = Set(name.to_string());
    am.menu_type = Set(menu_type.to_string());
    am.description = Set(description.map(|s| s.to_string()));
    am.path = Set(path.map(|s| s.to_string()));
    am.icon = Set(icon.map(|s| s.to_string()));
    am.order_num = Set(order_num);
    am.visible = Set(visible);
    am.parent_id = Set(Some(parent_id.to_string()));
    am.updated_at = Set(now_utc());
    am.update(db).await?;
    Ok(())
}

/// 部分更新权限记录(仅显式传入字段生效, 并刷新 updated_at)
pub async fn update(
    db: &DatabaseConnection,
    model: permission::Model,
    data: PermissionUpdate,
) -> Result<permission::Model, AppError> {
    let mut am: permission::ActiveModel = model.into();
    if let Some(v) = data.parent_id {
        am.parent_id = Set(Some(v));
    }
    if let Some(v) = data.name {
        am.name = Set(v);
    }
    if let Some(v) = data.code {
        am.code = Set(v);
    }
    if let Some(v) = data.description {
        am.description = Set(Some(v));
    }
    if let Some(v) = data.menu_type {
        am.menu_type = Set(v);
    }
    if let Some(v) = data.path {
        am.path = Set(Some(v));
    }
    if let Some(v) = data.component {
        am.component = Set(Some(v));
    }
    if let Some(v) = data.perms {
        am.perms = Set(Some(v));
    }
    if let Some(v) = data.icon {
        am.icon = Set(Some(v));
    }
    if let Some(v) = data.order_num {
        am.order_num = Set(v);
    }
    if let Some(v) = data.visible {
        am.visible = Set(v);
    }
    if let Some(v) = data.is_active {
        am.is_active = Set(v);
    }
    am.updated_at = Set(now_utc());
    Ok(am.update(db).await?)
}

/// 删除权限记录(返回是否实际删除)
pub async fn delete(db: &DatabaseConnection, permission_id: &str) -> Result<bool, AppError> {
    let result = permission::Entity::delete_by_id(permission_id).exec(db).await?;
    Ok(result.rows_affected > 0)
}

/// 全部权限(按 order_num 升序, 供树形组装)
pub async fn list_all(db: &DatabaseConnection) -> Result<Vec<permission::Model>, AppError> {
    Ok(permission::Entity::find()
        .order_by_asc(permission::Column::OrderNum)
        .all(db)
        .await?)
}

/// 分页查询权限列表(无过滤参数; 与 Python 一致无排序; 返回 (当前页数据, 总数))
pub async fn list_paged(
    db: &DatabaseConnection,
    offset: u64,
    limit: u64,
) -> Result<(Vec<permission::Model>, u64), AppError> {
    let total = permission::Entity::find().count(db).await?;
    let items = permission::Entity::find()
        .offset(offset)
        .limit(limit)
        .all(db)
        .await?;
    Ok((items, total))
}

/// 指定父权限下的子权限列表(按 order_num 升序)
pub async fn list_by_parent(
    db: &DatabaseConnection,
    parent_id: &str,
) -> Result<Vec<permission::Model>, AppError> {
    Ok(permission::Entity::find()
        .filter(permission::Column::ParentId.eq(parent_id))
        .order_by_asc(permission::Column::OrderNum)
        .all(db)
        .await?)
}
