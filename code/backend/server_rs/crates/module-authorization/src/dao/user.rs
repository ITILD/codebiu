//! 用户数据访问(对齐 Python dao/user.py)
//!
//! 查询辅助(get_by_username/get/count)按原服务层实现吞掉数据库异常,
//! 由调用方决定缺失语义(404/400/401), 保持迁移前后行为一致。

use sea_orm::{ActiveModelTrait, ColumnTrait, DatabaseConnection, EntityTrait, PaginatorTrait, QueryFilter, QueryOrder, QuerySelect, Select, Set};
use uuid::Uuid;

use crate::do_::entity::user;

use common::utils::error::AppError;

use crate::do_::now_utc;
use crate::do_::user::{UserCreate, UserUpdate};

/// 按用户名取用户(数据库异常按 None 处理, 与原实现一致)
pub async fn get_by_username(db: &DatabaseConnection, username: &str) -> Option<user::Model> {
    user::Entity::find()
        .filter(user::Column::Username.eq(username))
        .one(db)
        .await
        .ok()
        .flatten()
}

/// 按ID取用户(数据库异常按 None 处理, 与原实现一致)
pub async fn get(db: &DatabaseConnection, user_id: &str) -> Option<user::Model> {
    user::Entity::find_by_id(user_id).one(db).await.ok().flatten()
}

/// 用户总数(数据库异常按 0 处理, 与原实现一致)
pub async fn count(db: &DatabaseConnection) -> u64 {
    user::Entity::find().count(db).await.unwrap_or(0)
}

/// 插入用户记录(密码为调用方哈希后的密文)
pub async fn insert(
    db: &DatabaseConnection,
    data: UserCreate,
    password: String,
) -> Result<user::Model, AppError> {
    let now = now_utc();
    let am = user::ActiveModel {
        username: Set(data.username),
        password: Set(password),
        dept_id: Set(data.dept_id),
        email: Set(data.email),
        phone: Set(data.phone),
        nickname: Set(data.nickname),
        avatar: Set(data.avatar),
        is_active: Set(data.is_active.unwrap_or(true)),
        id: Set(Uuid::new_v4().simple().to_string()),
        created_at: Set(Some(now)),
        updated_at: Set(now),
    };
    Ok(am.insert(db).await?)
}

/// 部分更新用户记录(仅显式传入字段生效; password 为调用方哈希后的密文)
pub async fn update(
    db: &DatabaseConnection,
    model: user::Model,
    data: UserUpdate,
    password: Option<String>,
) -> Result<(), AppError> {
    let mut am: user::ActiveModel = model.into();
    if let Some(v) = data.username {
        am.username = Set(v);
    }
    if let Some(p) = password {
        am.password = Set(p);
    }
    if let Some(v) = data.dept_id {
        am.dept_id = Set(Some(v));
    }
    if let Some(v) = data.email {
        am.email = Set(Some(v));
    }
    if let Some(v) = data.phone {
        am.phone = Set(Some(v));
    }
    if let Some(v) = data.nickname {
        am.nickname = Set(Some(v));
    }
    if let Some(v) = data.avatar {
        am.avatar = Set(Some(v));
    }
    if let Some(v) = data.is_active {
        am.is_active = Set(v);
    }
    am.updated_at = Set(now_utc());
    am.update(db).await?;
    Ok(())
}

/// 删除用户记录(返回是否实际删除)
pub async fn delete(db: &DatabaseConnection, user_id: &str) -> Result<bool, AppError> {
    let result = user::Entity::delete_by_id(user_id).exec(db).await?;
    Ok(result.rows_affected > 0)
}

/// 更新用户头像字段(供头像服务直接读写; None 表示置空还原默认头像)
pub async fn update_avatar(
    db: &DatabaseConnection,
    user_id: &str,
    avatar: Option<String>,
) -> Result<(), AppError> {
    let model = user::Entity::find_by_id(user_id)
        .one(db)
        .await?
        .ok_or_else(|| AppError::not_found(format!("未找到ID为 {user_id} 的用户")))?;
    let mut am: user::ActiveModel = model.into();
    am.avatar = Set(avatar);
    am.updated_at = Set(now_utc());
    am.update(db).await?;
    Ok(())
}

/// 用户列表查询构建(用户名/昵称模糊, is_active 精确; 列表与计数共用)
fn user_select(
    username: Option<&str>,
    nickname: Option<&str>,
    is_active: Option<bool>,
) -> Select<user::Entity> {
    let mut select = user::Entity::find();
    if let Some(kw) = username {
        select = select.filter(user::Column::Username.contains(kw));
    }
    if let Some(kw) = nickname {
        select = select.filter(user::Column::Nickname.contains(kw));
    }
    if let Some(active) = is_active {
        select = select.filter(user::Column::IsActive.eq(active));
    }
    select
}

/// 分页查询用户列表(按创建时间升序; 返回 (当前页数据, 总数))
pub async fn list_paged(
    db: &DatabaseConnection,
    offset: u64,
    limit: u64,
    username: Option<&str>,
    nickname: Option<&str>,
    is_active: Option<bool>,
) -> Result<(Vec<user::Model>, u64), AppError> {
    let select = user_select(username, nickname, is_active);
    let total = select.clone().count(db).await?;
    let items = select
        .order_by_asc(user::Column::CreatedAt)
        .offset(offset)
        .limit(limit)
        .all(db)
        .await?;
    Ok((items, total))
}
