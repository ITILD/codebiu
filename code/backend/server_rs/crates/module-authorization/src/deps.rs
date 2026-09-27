//! 鉴权依赖(对齐 Python dependencies/auth.py + permission.py)
//!
//! - AuthUser: Bearer 令牌提取器(验证+黑名单+用户加载)
//! - authorize: casbin 权限校验(403 文案与 Python 一致)
//! - sync_default_user_roles: 新用户内置角色分配

use axum::extract::FromRequestParts;
use axum::http::request::Parts;
use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::security::jwt::verify_token as jwt_verify;
use crate::do_::entity::user;
use sea_orm::EntityTrait;

use crate::casbin_mgr::auth;
use crate::services::token as token_svc;

/// 模块内统一 Result 别名
type AppResult<T> = common::AppResult<T>;

/// 当前登录用户(经 Bearer 令牌验证后加载的完整用户)
#[derive(Debug, Clone)]
pub struct AuthUser(pub user::Model);

impl AuthUser {
    pub fn id(&self) -> &str {
        &self.0.id
    }
}

/// 从请求头解析 Bearer 令牌(缺失 → 401 "Not authenticated", 与 OAuth2PasswordBearer 一致)
fn bearer_token(parts: &Parts) -> AppResult<String> {
    let header = parts
        .headers
        .get(axum::http::header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .ok_or_else(|| AppError::unauthorized("Not authenticated"))?;
    header
        .strip_prefix("Bearer ")
        .map(|t| t.trim().to_string())
        .filter(|t| !t.is_empty())
        .ok_or_else(|| AppError::unauthorized("Not authenticated"))
}

/// 校验访问令牌并返回 user_id(黑名单 + JWT 验证)
pub async fn current_user_id(state: &AppState, token_str: &str) -> AppResult<String> {
    let config = token_svc::token_config(&state.settings).await?;
    // 黑名单检查(登出即时失效; 缓存异常降级不阻断)
    if state.token_blacklist.is_revoked(token_str) {
        return Err(AppError::unauthorized("令牌验证失败: 令牌已被吊销"));
    }
    let payload = jwt_verify(token_str, &config).map_err(|e| {
        AppError::unauthorized(format!("令牌验证失败: {e}"))
    })?;
    if payload.sub.is_empty() {
        return Err(AppError::unauthorized("令牌验证失败: 令牌中缺少用户ID"));
    }
    Ok(payload.sub)
}

/// 当前登录用户ID(轻量级身份校验, 不查库)
#[derive(Debug, Clone)]
pub struct AuthUserId(pub String);

impl FromRequestParts<AppState> for AuthUserId {
    type Rejection = AppError;

    async fn from_request_parts(parts: &mut Parts, state: &AppState) -> Result<Self, Self::Rejection> {
        let token_str = bearer_token(parts)?;
        let user_id = current_user_id(state, &token_str).await?;
        Ok(AuthUserId(user_id))
    }
}

impl FromRequestParts<AppState> for AuthUser {
    type Rejection = AppError;

    async fn from_request_parts(parts: &mut Parts, state: &AppState) -> Result<Self, Self::Rejection> {
        let token_str = bearer_token(parts)?;
        let user_id = current_user_id(state, &token_str)
            .await
            .map_err(|e| AppError::unauthorized(format!("获取当前用户失败: {}", e)))?;
        let u = user::Entity::find_by_id(&user_id)
            .one(&state.db)
            .await?
            .ok_or_else(|| {
                // 令牌有效但用户已删除: 统一按认证失败处理
                AppError::unauthorized("获取当前用户失败: 用户不存在")
            })?;
        Ok(AuthUser(u))
    }
}

/// 可选登录用户ID(对齐 Python dependencies/filesystem.py 的 get_download_user_id)
///
/// 未携带/令牌无效 → None(不直接 401), 由调用方按业务口径决定匿名/401/403
#[derive(Debug, Clone)]
pub struct AuthUserIdOptional(pub Option<String>);

impl FromRequestParts<AppState> for AuthUserIdOptional {
    type Rejection = std::convert::Infallible;

    async fn from_request_parts(parts: &mut Parts, state: &AppState) -> Result<Self, Self::Rejection> {
        let user_id = match bearer_token(parts) {
            Ok(token_str) => current_user_id(state, &token_str).await.ok(),
            Err(_) => None,
        };
        Ok(AuthUserIdOptional(user_id))
    }
}

/// casbin 权限校验(无权限 → 403, 文案与 Python 一致)
pub async fn authorize(user_id: &str, dom: &str, obj: &str, act: &str) -> AppResult<()> {
    if !auth().enforce(user_id, dom, obj, act).await {
        return Err(AppError::forbidden(format!("无操作权限: {dom}/{obj}/{act}")));
    }
    Ok(())
}

/// 为新用户分配内置角色(首个用户引导为全局管理员; 其余绑定 user 角色)
pub async fn sync_default_user_roles(user_id: &str, is_first_user: bool) {
    let manager = auth();
    if !manager.ready().await {
        tracing::warn!("Casbin enforcer 未初始化,跳过默认角色分配");
        return;
    }
    // 首个注册用户引导为全局管理员(全局域 "*" 的 admin 角色)
    if is_first_user && !manager.has_grouping_policy(user_id, "admin", "*").await {
        if let Err(e) = manager.add_grouping_policy(vec![user_id.into(), "admin".into(), "*".into()]).await {
            tracing::error!("分配管理员角色失败: {e}");
        }
        tracing::info!("首个用户 {user_id} 已引导为全局管理员");
    }
    if !manager.has_grouping_policy(user_id, "user", "*").await {
        if let Err(e) = manager.add_grouping_policy(vec![user_id.into(), "user".into(), "*".into()]).await {
            tracing::error!("分配默认角色失败: {e}");
        }
    }
}

/// 注册流程是否开启邮箱验证(email.use_for_register)
pub async fn email_verify_enabled(state: &AppState) -> AppResult<bool> {
    let email: common::config::dynamic::EmailSettings = state.settings.get("email").await?;
    Ok(email.use_for_register)
}
