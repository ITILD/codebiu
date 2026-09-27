//! 令牌服务(对齐 Python service/token.py)
//!
//! - access 令牌不落库; refresh 令牌落 token 表(id 即 token_id)
//! - 刷新令牌验证须查库确认未撤销
//! - 密钥/有效期每次从动态配置中心读取(改配置即时生效)
//! - 数据库读写委托 dao::token

use sea_orm::DatabaseConnection;

use common::config::dynamic::TokenSettings;
use common::utils::error::AppError;
use common::utils::security::jwt::{create_token, token_expiry, verify_token as jwt_verify, TokenType};

use crate::dao;
use crate::do_::auth::TokenResponseBase;

/// 由动态配置构建 JWT 配置
pub async fn token_config(
    settings: &common::config::dynamic::SettingsService,
) -> Result<common::utils::security::jwt::TokenConfig, AppError> {
    let cfg: TokenSettings = settings.get("token").await?;
    Ok(common::utils::security::jwt::TokenConfig {
        secret: cfg.secret_key,
        algorithm: cfg.algorithm,
        expire_minutes: cfg.expire_minutes,
        refresh_expire_days: cfg.refresh_expire_days,
    })
}

/// 创建令牌(access 不落库; refresh 落库并返回 token_id)
///
/// extra 为并入 JWT 载荷的附加数据(对齐 Python additional_data)
pub async fn create_token_response(
    db: &DatabaseConnection,
    config: &common::utils::security::jwt::TokenConfig,
    user_id: &str,
    token_type: TokenType,
    extra: serde_json::Value,
) -> Result<TokenResponseBase, AppError> {
    let jwt = create_token(user_id, token_type, config, extra).map_err(AppError::business)?;
    let (expires_at, expires_in) = token_expiry(token_type, config);

    let mut token_id: Option<String> = None;
    // 只保存刷新令牌信息, 访问令牌不保存
    if token_type == TokenType::Refresh {
        let id = dao::token::insert_refresh(db, user_id, &jwt, expires_in as i32, expires_at.fixed_offset()).await?;
        token_id = Some(id);
    }
    Ok(TokenResponseBase { token: jwt, expires_in, token_id })
}

/// 验证令牌(签名+过期+黑名单外置; refresh 类型查库确认未撤销)
///
/// 失败返回与 Python 一致的文案: "Token has expired" / "Invalid token" / "Token has been revoked"
pub async fn verify(
    db: &DatabaseConnection,
    config: &common::utils::security::jwt::TokenConfig,
    token_str: &str,
    expected: TokenType,
) -> Result<common::utils::security::jwt::Claims, String> {
    let payload = jwt_verify(token_str, config)?;
    let user_id = payload.sub.clone();
    if user_id.is_empty() {
        return Err("Invalid token".to_string());
    }
    // 刷新令牌必须检查数据库状态(是否被撤销)
    if expected == TokenType::Refresh {
        let info = dao::token::get_by_user_id(db, &user_id).await;
        match info {
            Some(row) if !row.is_revoked => {}
            _ => return Err("Token has been revoked".to_string()),
        }
    }
    Ok(payload)
}

/// 按令牌字符串取记录(供 /info 端点; 数据库异常按 None 处理, 与原实现一致)
pub async fn get_by_token(db: &DatabaseConnection, token_str: &str) -> Option<crate::do_::entity::token::Model> {
    dao::token::get_by_token(db, token_str).await
}

/// 按 token_id 撤销(置 is_revoked=true)
pub async fn revoke_by_token_id(db: &DatabaseConnection, token_id: &str) -> Result<bool, AppError> {
    dao::token::revoke_by_token_id(db, token_id).await
}

/// 删除用户全部令牌(revoke-all 语义)
pub async fn delete_by_user_id(db: &DatabaseConnection, user_id: &str) -> Result<u64, AppError> {
    dao::token::delete_by_user_id(db, user_id).await
}
