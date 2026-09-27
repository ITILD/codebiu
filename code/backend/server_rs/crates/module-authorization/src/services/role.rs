//! 角色服务(对齐 Python service/role.py)
//!
//! 业务规则: 不存在按 404 处理(文案与 Python 一致); 数据库读写委托 dao::role。

use sea_orm::DatabaseConnection;

use crate::do_::entity::role;

use common::utils::error::AppError;
use common::utils::pagination::{PaginationParams, PaginationResponse};

use crate::dao;
use crate::do_::role::{RoleCreate, RoleUpdate};

/// 创建角色(返回创建的记录, 默认 data_scope="1"/is_active=true)
pub async fn create(db: &DatabaseConnection, data: RoleCreate) -> Result<role::Model, AppError> {
    dao::role::insert(db, data).await
}

/// 分页查询角色列表(名称/权限字符模糊, 状态精确; 与 Python 一致无排序)
pub async fn list_paged(
    db: &DatabaseConnection,
    pagination: &PaginationParams,
    name: Option<String>,
    role_key: Option<String>,
    is_active: Option<bool>,
) -> Result<PaginationResponse<role::Model>, AppError> {
    let (items, total) = dao::role::list_paged(
        db,
        pagination.offset(),
        pagination.limit(),
        name.as_deref(),
        role_key.as_deref(),
        is_active,
    )
    .await?;
    Ok(PaginationResponse::create(items, total as i64, pagination))
}

/// 全部角色(不分页, 按 sort 升序, 用于下拉选择)
pub async fn list_all(db: &DatabaseConnection) -> Result<Vec<role::Model>, AppError> {
    dao::role::list_all(db).await
}

/// 按ID获取角色(不存在 404 "角色不存在")
pub async fn get(db: &DatabaseConnection, role_id: &str) -> Result<role::Model, AppError> {
    dao::role::get(db, role_id)
        .await?
        .ok_or_else(|| AppError::not_found("角色不存在"))
}

/// 按角色名称精确查询(不存在 404 "角色不存在")
pub async fn get_by_name(db: &DatabaseConnection, name: &str) -> Result<role::Model, AppError> {
    dao::role::find_by_name(db, name)
        .await?
        .ok_or_else(|| AppError::not_found("角色不存在"))
}

/// 按权限字符串查询(不存在 404 "角色不存在")
pub async fn get_by_key(db: &DatabaseConnection, role_key: &str) -> Result<role::Model, AppError> {
    dao::role::find_by_key(db, role_key)
        .await?
        .ok_or_else(|| AppError::not_found("角色不存在"))
}

/// 部分更新角色(不存在 404)
pub async fn update(db: &DatabaseConnection, role_id: &str, data: RoleUpdate) -> Result<(), AppError> {
    let model = dao::role::get(db, role_id)
        .await?
        .ok_or_else(|| AppError::not_found(format!("未找到ID为 {role_id} 的角色")))?;
    dao::role::update(db, model, data).await?;
    Ok(())
}

/// 删除角色(不存在 404)
pub async fn delete(db: &DatabaseConnection, role_id: &str) -> Result<(), AppError> {
    if !dao::role::delete(db, role_id).await? {
        return Err(AppError::not_found(format!("未找到ID为 {role_id} 的角色")));
    }
    Ok(())
}
