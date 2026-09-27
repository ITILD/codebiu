//! 用户服务(对齐 Python service/user.py)
//!
//! 业务规则: 用户名重复 409、用户不存在 400(与 Python dao 层行为一致)、密码哈希、
//! 认证校验; 数据库读写全部委托 dao::user。

use sea_orm::DatabaseConnection;

use crate::do_::entity::user;

use common::utils::error::AppError;
use common::utils::pagination::{PaginationParams, PaginationResponse};
use common::utils::security::password::{hash_password, verify_password};

use crate::dao;
use crate::do_::user::{UserCreate, UserUpdate};

/// 按用户名取用户(数据库异常按 None 处理, 与原实现一致)
pub async fn get_by_username(db: &DatabaseConnection, username: &str) -> Option<user::Model> {
    dao::user::get_by_username(db, username).await
}

/// 按ID取用户(数据库异常按 None 处理, 与原实现一致)
pub async fn get(db: &DatabaseConnection, user_id: &str) -> Option<user::Model> {
    dao::user::get(db, user_id).await
}

/// 用户总数(数据库异常按 0 处理, 与原实现一致)
pub async fn count(db: &DatabaseConnection) -> u64 {
    dao::user::count(db).await
}

/// 创建用户(密码哈希; 不含角色分配, 调用方负责 sync_default_user_roles)
///
/// 用户名重复返回 409 Conflict。
pub async fn create(db: &DatabaseConnection, data: UserCreate) -> Result<user::Model, AppError> {
    if get_by_username(db, &data.username).await.is_some() {
        return Err(AppError::Conflict(format!("用户名 '{}' 已存在", data.username)));
    }
    let password = hash_password(&data.password).map_err(AppError::business)?;
    dao::user::insert(db, data, password).await
}

/// 部分更新(密码传入时自动哈希; 用户不存在按 400 处理, 与 Python dao 层行为一致)
pub async fn update(db: &DatabaseConnection, user_id: &str, data: UserUpdate) -> Result<(), AppError> {
    let model = get(db, user_id)
        .await
        .ok_or_else(|| AppError::business("用户不存在"))?;
    let password = match data.password.as_deref() {
        Some(p) => Some(hash_password(p).map_err(AppError::business)?),
        None => None,
    };
    dao::user::update(db, model, data, password).await
}

/// 删除用户(不存在按 400 处理)
pub async fn delete(db: &DatabaseConnection, user_id: &str) -> Result<(), AppError> {
    if !dao::user::delete(db, user_id).await? {
        return Err(AppError::business("用户不存在"));
    }
    Ok(())
}

/// 分页列表(username/nickname 模糊, is_active 精确; 按创建时间升序)
pub async fn list_paged(
    db: &DatabaseConnection,
    pagination: &PaginationParams,
    username: Option<String>,
    nickname: Option<String>,
    is_active: Option<bool>,
) -> Result<PaginationResponse<user::Model>, AppError> {
    let (items, total) = dao::user::list_paged(
        db,
        pagination.offset(),
        pagination.limit(),
        username.as_deref(),
        nickname.as_deref(),
        is_active,
    )
    .await?;
    Ok(PaginationResponse::create(items, total as i64, pagination))
}

/// 认证(用户名+密码校验, 失败返回 None)
pub async fn authenticate(
    db: &DatabaseConnection,
    username: &str,
    password: &str,
) -> Option<user::Model> {
    let user = get_by_username(db, username).await?;
    if verify_password(password, &user.password) {
        Some(user)
    } else {
        None
    }
}
