//! 令牌数据访问(对齐 Python dao/token.py)
//!
//! 表内仅存 refresh 令牌记录(id 即 token_id); 查询辅助按原实现吞掉数据库异常。

use chrono::{DateTime, FixedOffset};
use sea_orm::{ActiveModelTrait, ColumnTrait, DatabaseConnection, EntityTrait, QueryFilter, Set};
use sea_orm::sea_query::Expr;
use uuid::Uuid;

use crate::do_::entity::token;
use crate::do_::entity::sea_orm_active_enums::Tokentype;

use common::utils::error::AppError;

use crate::do_::now_utc;

/// 按用户取令牌记录(表内仅存 refresh, 查询语义与 Python 一致: 按用户取首条;
/// 数据库异常按 None 处理, 与原实现一致)
pub async fn get_by_user_id(db: &DatabaseConnection, user_id: &str) -> Option<token::Model> {
    token::Entity::find()
        .filter(token::Column::UserId.eq(user_id))
        .one(db)
        .await
        .ok()
        .flatten()
}

/// 按令牌字符串取记录(数据库异常按 None 处理, 与原实现一致)
pub async fn get_by_token(db: &DatabaseConnection, token_str: &str) -> Option<token::Model> {
    token::Entity::find()
        .filter(token::Column::Token.eq(token_str))
        .one(db)
        .await
        .ok()
        .flatten()
}

/// 插入刷新令牌记录, 返回新生成的 token_id
pub async fn insert_refresh(
    db: &DatabaseConnection,
    user_id: &str,
    jwt: &str,
    expires_in: i32,
    expires_at: DateTime<FixedOffset>,
) -> Result<String, AppError> {
    let now = now_utc();
    let id = Uuid::new_v4().simple().to_string();
    let am = token::ActiveModel {
        user_id: Set(user_id.to_string()),
        token: Set(jwt.to_string()),
        token_type: Set(Tokentype::Refresh),
        expires_in: Set(expires_in),
        expires_at: Set(Some(expires_at)),
        is_revoked: Set(false),
        id: Set(id.clone()),
        created_at: Set(Some(now)),
        updated_at: Set(now),
    };
    am.insert(db).await?;
    Ok(id)
}

/// 按 token_id 撤销(置 is_revoked=true), 返回是否命中记录
pub async fn revoke_by_token_id(
    db: &DatabaseConnection,
    token_id: &str,
) -> Result<bool, AppError> {
    let result = token::Entity::update_many()
        .col_expr(token::Column::IsRevoked, Expr::value(true))
        .filter(token::Column::Id.eq(token_id))
        .exec(db)
        .await?;
    Ok(result.rows_affected > 0)
}

/// 删除用户全部令牌(revoke-all 语义), 返回删除行数
pub async fn delete_by_user_id(db: &DatabaseConnection, user_id: &str) -> Result<u64, AppError> {
    let result = token::Entity::delete_many()
        .filter(token::Column::UserId.eq(user_id))
        .exec(db)
        .await?;
    Ok(result.rows_affected)
}
