//! 认证控制器(对齐 Python controller/auth.py)
//!
//! 路由前缀 /authorization/auth: 登录/注册/登出/刷新/当前用户信息。
//! 说明: /me/avatar 上传与删除依赖文件模块(P3 迁移), 届时补齐。

use axum::extract::{FromRequest, Multipart, Request, State};
use axum::http::{header::CONTENT_TYPE, StatusCode};
use axum::Json;
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::BTreeMap;

use crate::casbin_mgr::auth;
use crate::deps::{email_verify_enabled, AuthUser, AuthUserId};
use crate::do_::auth::{
    AuthLogoutRequest, AuthResponse, PasswordChange, RefreshTokenRequest, RegisterCodeRequest,
    RegisterConfigResponse, RegisterRequest, SelfProfileUpdate, TokenResponseBase,
    TokenResponseFull,
};
use crate::do_::user::{UserCreate, UserResponse, UserUpdate};
use crate::perms;
use crate::services::token as token_svc;
use crate::services::user as user_svc;
use common::utils::extract::AppJson;
use common::runtime::AppState;
use common::config::dynamic::TokenSettings;
use common::utils::error::AppError;
use common::utils::security::jwt::{verify_token as jwt_verify, TokenType};
use crate::do_::entity::user;

/// OAuth2 登录表单(兼容 urlencoded 与 multipart 两种编码, 对齐 OAuth2PasswordRequestForm)
#[derive(Debug, Clone, Deserialize)]
pub struct OAuth2Form {
    username: String,
    password: String,
}

impl<S: Send + Sync> FromRequest<S> for OAuth2Form {
    type Rejection = AppError;

    async fn from_request(req: Request, state: &S) -> Result<Self, Self::Rejection> {
        let is_multipart = req
            .headers()
            .get(CONTENT_TYPE)
            .and_then(|v| v.to_str().ok())
            .map(|ct| ct.starts_with("multipart/form-data"))
            .unwrap_or(false);
        if !is_multipart {
            let form: axum::Form<OAuth2Form> = axum::Form::from_request(req, state)
                .await
                .map_err(|_| AppError::validation(&["body", "username"], "解析登录表单失败"))?;
            return Ok(form.0);
        }
        // multipart 编码: 逐字段提取 username/password
        let mut multipart = Multipart::from_request(req, state)
            .await
            .map_err(|_| AppError::business("解析登录表单失败"))?;
        let (mut username, mut password) = (None, None);
        while let Some(field) = multipart
            .next_field()
            .await
            .map_err(|e| AppError::business(format!("解析登录表单失败: {e}")))?
        {
            match field.name().unwrap_or_default() {
                "username" => {
                    username = Some(
                        field
                            .text()
                            .await
                            .map_err(|e| AppError::business(format!("解析登录表单失败: {e}")))?,
                    )
                }
                "password" => {
                    password = Some(
                        field
                            .text()
                            .await
                            .map_err(|e| AppError::business(format!("解析登录表单失败: {e}")))?,
                    )
                }
                _ => {}
            }
        }
        Ok(Self {
            username: username.ok_or_else(|| {
                AppError::validation(&["body", "username"], "字段缺失")
            })?,
            password: password.ok_or_else(|| {
                AppError::validation(&["body", "password"], "字段缺失")
            })?,
        })
    }
}

/// 为用户签发 access/refresh 双令牌(登录与注册共用)
async fn create_full_tokens(state: &AppState, user_id: &str) -> Result<TokenResponseFull, AppError> {
    let config = token_svc::token_config(&state.settings).await?;
    let access = token_svc::create_token_response(
        &state.db, &config, user_id, TokenType::Access, Value::Null,
    )
    .await?;
    let refresh = token_svc::create_token_response(
        &state.db, &config, user_id, TokenType::Refresh, Value::Null,
    )
    .await?;
    Ok(TokenResponseFull { access, refresh })
}

/// GET /me —— 获取当前登录用户完整信息(实体序列化, 与 Python 返回 User 模型一致)
pub async fn get_me(AuthUser(u): AuthUser) -> Json<user::Model> {
    Json(u)
}

/// GET /me-id —— 获取当前登录用户ID(轻量级身份校验)
pub async fn get_me_id(AuthUserId(uid): AuthUserId) -> String {
    uid
}

/// PUT /me —— 自助更新个人资料(昵称/邮箱/电话/头像)
pub async fn update_my_profile(
    state: State<AppState>,
    AuthUser(u): AuthUser,
    AppJson(profile): AppJson<SelfProfileUpdate>,
) -> Result<Json<UserResponse>, AppError> {
    let update = UserUpdate {
        username: None,
        password: None,
        dept_id: None,
        email: profile.email,
        phone: profile.phone,
        nickname: profile.nickname,
        avatar: profile.avatar,
        is_active: None,
    };
    user_svc::update(&state.db, &u.id, update).await?;
    let updated = user_svc::get(&state.db, &u.id)
        .await
        .ok_or_else(|| AppError::business("用户不存在"))?;
    Ok(Json(UserResponse::from(updated)))
}

/// PUT /me/password —— 自助修改密码(需验证旧密码, 成功 204)
pub async fn change_my_password(
    state: State<AppState>,
    AuthUser(u): AuthUser,
    AppJson(pc): AppJson<PasswordChange>,
) -> Result<StatusCode, AppError> {
    if !common::utils::security::password::verify_password(&pc.old_password, &u.password) {
        return Err(AppError::business("旧密码错误"));
    }
    if pc.old_password == pc.new_password {
        return Err(AppError::business("新密码不能与旧密码相同"));
    }
    let update = UserUpdate {
        password: Some(pc.new_password),
        ..Default::default()
    };
    user_svc::update(&state.db, &u.id, update).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// GET /me-permissions —— 当前用户角色(按域分组)与权限码列表
///
/// 全局管理员 permissions 返回 ["*"]; 普通用户逐条校验声明节点后收集。
pub async fn get_my_permissions(AuthUserId(uid): AuthUserId) -> Json<Value> {
    let manager = auth();
    if !manager.ready().await {
        return Json(json!({ "roles": {}, "permissions": [] }));
    }
    // 角色绑定: 遍历用户-角色绑定规则, 按域分组
    let mut roles: BTreeMap<String, Vec<String>> = BTreeMap::new();
    for g in manager.get_grouping_policies(None).await {
        if g.len() >= 3 && g[0] == uid.as_str() {
            roles.entry(g[2].clone()).or_default().push(g[1].clone());
        }
    }
    // 权限码展开: 全局管理员直接返回通配符
    let is_global_admin = roles
        .get("*")
        .map(|r| r.iter().any(|k| k == "admin"))
        .unwrap_or(false);
    if is_global_admin {
        return Json(json!({ "roles": roles, "permissions": ["*"] }));
    }
    let mut permissions: Vec<String> = Vec::new();
    for (dom, obj, act) in perms::iter_node_policies() {
        if manager.enforce(&uid, &dom, &obj, &act).await {
            permissions.push(format!("{dom}:{obj}:{act}"));
        }
    }
    Json(json!({ "roles": roles, "permissions": permissions }))
}

/// GET /register-config —— 注册流程配置(是否开启邮箱验证码)
pub async fn get_register_config(state: State<AppState>) -> Result<Json<RegisterConfigResponse>, AppError> {
    Ok(Json(RegisterConfigResponse {
        email_verify: email_verify_enabled(&state).await?,
    }))
}

/// POST /register/code —— 发送注册邮箱验证码
///
/// 说明: 邮件发送服务由 module_contact 提供(P4 阶段迁移); 当前未开启邮箱验证时
/// 返回与 Python 一致的 400 文案, 开启时因邮件服务未就绪返回发送失败。
pub async fn send_register_code(
    state: State<AppState>,
    AppJson(req): AppJson<RegisterCodeRequest>,
) -> Result<Json<bool>, AppError> {
    let _ = &req.email;
    if !email_verify_enabled(&state).await? {
        return Err(AppError::business("未开启注册邮箱验证"));
    }
    Err(AppError::business("验证码邮件发送失败, 请稍后重试"))
}

/// POST /register —— 注册用户并直接返回登录态(首个用户自动引导为全局管理员)
pub async fn register(
    state: State<AppState>,
    AppJson(req): AppJson<RegisterRequest>,
) -> Result<Json<AuthResponse>, AppError> {
    // 开启邮箱验证时先校验验证码(邮件服务 P4 迁移, 当前一律拒绝)
    if email_verify_enabled(&state).await? {
        return Err(match req.code {
            None => AppError::business("请填写邮箱验证码"),
            Some(_) => AppError::business("验证码错误或已过期"),
        });
    }
    let is_first_user = user_svc::count(&state.db).await == 0;
    let created = user_svc::create(
        &state.db,
        UserCreate {
            username: req.username,
            password: req.password,
            dept_id: None,
            email: req.email,
            phone: req.phone,
            nickname: req.nickname,
            avatar: None,
            is_active: None,
        },
    )
    .await?;
    // 分配内置角色(失败不影响用户创建)
    crate::deps::sync_default_user_roles(&created.id, is_first_user).await;
    let tokens = create_full_tokens(&state, &created.id).await?;
    Ok(Json(AuthResponse::new(tokens, UserResponse::from(created))))
}

/// 校验凭据并返回用户(登录与 OAuth2 调试端点共用; 失败文案与 Python 一致)
async fn authenticate_or_401(state: &AppState, username: &str, password: &str) -> Result<user::Model, AppError> {
    let user = user_svc::authenticate(&state.db, username, password)
        .await
        .ok_or_else(|| AppError::unauthorized("用户名或密码错误"))?;
    if !user.is_active {
        return Err(AppError::unauthorized("用户账户已被禁用"));
    }
    Ok(user)
}

/// POST /login —— 登录获取访问令牌(401 文案与 Python 一致)
pub async fn login(
    state: State<AppState>,
    form: OAuth2Form,
) -> Result<Json<AuthResponse>, AppError> {
    let user = authenticate_or_401(&state, &form.username, &form.password).await?;
    let tokens = create_full_tokens(&state, &user.id).await?;
    Ok(Json(AuthResponse::new(tokens, UserResponse::from(user))))
}

/// POST /token —— OAuth2 标准登录(Swagger Authorize 专用)
pub async fn login_for_oauth2(
    state: State<AppState>,
    form: OAuth2Form,
) -> Result<Json<Value>, AppError> {
    let user = authenticate_or_401(&state, &form.username, &form.password).await?;
    let config = token_svc::token_config(&state.settings).await?;
    let access = token_svc::create_token_response(
        &state.db, &config, &user.id, TokenType::Access, Value::Null,
    )
    .await?;
    Ok(Json(json!({ "access_token": access.token, "token_type": "bearer" })))
}

/// POST /logout —— 登出(访问令牌写入黑名单立即失效 + 撤销刷新令牌)
pub async fn logout(
    state: State<AppState>,
    AppJson(req): AppJson<AuthLogoutRequest>,
) -> Result<Json<bool>, AppError> {
    let config = token_svc::token_config(&state.settings).await?;
    // 验证访问令牌有效性(无效/已吊销 → 401, 防止重复登出)
    let valid = !state.token_blacklist.is_revoked(&req.token_access)
        && jwt_verify(&req.token_access, &config).is_ok();
    if !valid {
        return Err(AppError::unauthorized("访问令牌无效"));
    }
    // 黑名单 TTL 与访问令牌有效期对齐(取当前动态配置)
    let token_cfg: TokenSettings = state.settings.get("token").await?;
    state
        .token_blacklist
        .revoke(&req.token_access, token_cfg.expire_minutes * 60);
    // 撤销配套刷新令牌(无效不阻断登出)
    let _ = token_svc::revoke_by_token_id(&state.db, &req.token_refresh_id).await;
    Ok(Json(true))
}

/// POST /refresh —— 校验刷新令牌并签发新的访问令牌(刷新令牌不轮换; 失败 401)
pub async fn refresh(
    state: State<AppState>,
    AppJson(req): AppJson<RefreshTokenRequest>,
) -> Result<Json<TokenResponseBase>, AppError> {
    let config = token_svc::token_config(&state.settings).await?;
    let payload = token_svc::verify(&state.db, &config, &req.token_refresh, TokenType::Refresh)
        .await
        .map_err(|e| AppError::unauthorized(format!("Invalid refresh token: {e}")))?;
    let user = user_svc::get(&state.db, &payload.sub)
        .await
        .ok_or_else(|| AppError::unauthorized("Invalid refresh token: 用户不存在"))?;
    if !user.is_active {
        return Err(AppError::unauthorized("Invalid refresh token: 用户账户已被禁用"));
    }
    let access = token_svc::create_token_response(
        &state.db, &config, &user.id, TokenType::Access, Value::Null,
    )
    .await?;
    Ok(Json(access))
}

/// 认证模块路由(挂载到 /authorization/auth)
pub fn router() -> axum::Router<common::runtime::AppState> {
    use axum::routing::{get, post, put};
    axum::Router::new()
        .route("/me", get(get_me).put(update_my_profile))
        .route("/me-id", get(get_me_id))
        .route("/me/password", put(change_my_password))
        .route("/me-permissions", get(get_my_permissions))
        .route("/register-config", get(get_register_config))
        .route("/register/code", post(send_register_code))
        .route("/register", post(register))
        .route("/login", post(login))
        .route("/token", post(login_for_oauth2))
        .route("/logout", post(logout))
        .route("/refresh", post(refresh))
}
