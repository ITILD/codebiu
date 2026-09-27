//! 用户管理控制器(对齐 Python controller/user.py)
//!
//! 路由前缀 /authorization/users: CRUD + 分页列表 + 认证。
//! 控制器只做请求解析/权限校验/响应包装, 业务规则与数据读写分别在 services/dao 层。

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::Json;
use serde::Deserialize;

use crate::deps::{authorize, sync_default_user_roles, AuthUser};
use crate::do_::user::{UserCreate, UserResponse, UserUpdate};
use crate::services::user as user_svc;
use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::extract::{AppJson, AppQuery};
use common::utils::pagination::{PaginationParams, PaginationResponse};
use crate::do_::entity::user;

/// sys:user 资源权限校验(全部端点共用)
async fn require_perm(user: &user::Model, act: &str) -> Result<(), AppError> {
    authorize(&user.id, "sys", "user", act).await
}

/// POST "" —— 创建用户(201; 返回 UserResponse; 首个用户自动引导为全局管理员)
pub async fn create_user(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppJson(data): AppJson<UserCreate>,
) -> Result<(StatusCode, Json<UserResponse>), AppError> {
    require_perm(&actor, "create").await?;
    let is_first_user = user_svc::count(&state.db).await == 0;
    let created = user_svc::create(&state.db, data).await?;
    // 分配内置角色(失败不影响用户创建, 与 Python service.add 行为一致)
    sync_default_user_roles(&created.id, is_first_user).await;
    Ok((StatusCode::CREATED, Json(UserResponse::from(created))))
}

/// GET /list 查询参数
#[derive(Debug, Deserialize)]
pub struct UserListQuery {
    #[serde(default)]
    pub username: Option<String>,
    #[serde(default)]
    pub nickname: Option<String>,
    #[serde(default)]
    pub is_active: Option<bool>,
}

/// GET /list —— 分页查询用户列表(用户名/昵称模糊, 状态精确)
pub async fn list_users(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppQuery(pagination): AppQuery<PaginationParams>,
    AppQuery(query): AppQuery<UserListQuery>,
) -> Result<Json<PaginationResponse<user::Model>>, AppError> {
    require_perm(&actor, "read").await?;
    pagination.validate()?;
    let page = user_svc::list_paged(
        &state.db,
        &pagination,
        query.username,
        query.nickname,
        query.is_active,
    )
    .await?;
    Ok(Json(page))
}

/// GET /{user_id} —— 获取单个用户(实体序列化, 与 Python 返回 User 模型一致)
pub async fn get_user(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(user_id): Path<String>,
) -> Result<Json<user::Model>, AppError> {
    require_perm(&actor, "read").await?;
    let user = user_svc::get(&state.db, &user_id)
        .await
        .ok_or_else(|| AppError::not_found("用户不存在"))?;
    Ok(Json(user))
}

/// DELETE /{user_id} —— 删除用户(204; 不存在 400)
pub async fn delete_user(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(user_id): Path<String>,
) -> Result<StatusCode, AppError> {
    require_perm(&actor, "delete").await?;
    user_svc::delete(&state.db, &user_id).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// PUT /{user_id} —— 部分更新用户(204; 密码自动哈希; 不存在 400)
pub async fn update_user(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(user_id): Path<String>,
    AppJson(data): AppJson<UserUpdate>,
) -> Result<StatusCode, AppError> {
    require_perm(&actor, "update").await?;
    user_svc::update(&state.db, &user_id, data).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// POST /authenticate 查询参数
#[derive(Debug, Deserialize)]
pub struct AuthQuery {
    pub username: String,
    pub password: String,
}

/// POST /authenticate —— 用户名密码认证(凭据错误 401 "Invalid credentials")
pub async fn authenticate_user(
    state: State<AppState>,
    AppQuery(q): AppQuery<AuthQuery>,
) -> Result<Json<user::Model>, AppError> {
    let user = user_svc::authenticate(&state.db, &q.username, &q.password)
        .await
        .ok_or_else(|| AppError::unauthorized("Invalid credentials"))?;
    Ok(Json(user))
}

/// 用户管理路由(挂载到 /authorization/users)
pub fn router() -> axum::Router<common::runtime::AppState> {
    use axum::routing::{get, post};
    axum::Router::new()
        .route("/", post(create_user))
        .route("/list", get(list_users))
        .route("/authenticate", post(authenticate_user))
        .route(
            // 一级动态段统一命名 resource_id(axum merge 时不同名的同级动态段会冲突)
            "/{resource_id}",
            get(get_user).delete(delete_user).put(update_user),
        )
}
