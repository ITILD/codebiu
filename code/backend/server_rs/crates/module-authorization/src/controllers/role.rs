//! 角色管理控制器(对齐 Python controller/role.py)
//!
//! 路由前缀 /authorization/roles: CRUD + 分页/全量列表 + 按名称/权限字符查询。
//! 控制器只做请求解析/权限校验/响应包装, 业务规则与数据读写分别在 services/dao 层。

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::Json;
use serde::Deserialize;

use crate::deps::{authorize, AuthUser};
use crate::do_::role::{RoleCreate, RoleUpdate};
use crate::services::role as role_svc;
use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::extract::{AppJson, AppQuery};
use common::utils::pagination::{PaginationParams, PaginationResponse};
use crate::do_::entity::{role, user};

/// sys:role 资源权限校验
async fn require_perm(user: &user::Model, act: &str) -> Result<(), AppError> {
    authorize(&user.id, "sys", "role", act).await
}

/// POST "" —— 创建角色(201; 返回角色ID)
pub async fn create_role(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppJson(data): AppJson<RoleCreate>,
) -> Result<(StatusCode, Json<String>), AppError> {
    require_perm(&actor, "create").await?;
    let created = role_svc::create(&state.db, data).await?;
    Ok((StatusCode::CREATED, Json(created.id)))
}

/// GET /list 查询参数
#[derive(Debug, Deserialize)]
pub struct RoleListQuery {
    #[serde(default)]
    pub name: Option<String>,
    #[serde(default)]
    pub role_key: Option<String>,
    #[serde(default)]
    pub is_active: Option<bool>,
}

/// GET /list —— 分页查询角色列表(名称/权限字符模糊, 状态精确; 与 Python 一致无排序)
pub async fn list_roles(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppQuery(pagination): AppQuery<PaginationParams>,
    AppQuery(query): AppQuery<RoleListQuery>,
) -> Result<Json<PaginationResponse<role::Model>>, AppError> {
    require_perm(&actor, "read").await?;
    pagination.validate()?;
    let page = role_svc::list_paged(
        &state.db,
        &pagination,
        query.name,
        query.role_key,
        query.is_active,
    )
    .await?;
    Ok(Json(page))
}

/// GET /all —— 全部角色(不分页, 按 sort 升序, 用于下拉选择)
pub async fn list_all_roles(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
) -> Result<Json<Vec<role::Model>>, AppError> {
    require_perm(&actor, "read").await?;
    let items = role_svc::list_all(&state.db).await?;
    Ok(Json(items))
}

/// GET /{role_id} —— 获取单个角色(不存在 404 "角色不存在")
pub async fn get_role(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(role_id): Path<String>,
) -> Result<Json<role::Model>, AppError> {
    require_perm(&actor, "read").await?;
    let role = role_svc::get(&state.db, &role_id).await?;
    Ok(Json(role))
}

/// DELETE /{role_id} —— 删除角色(204; 不存在 404)
pub async fn delete_role(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(role_id): Path<String>,
) -> Result<StatusCode, AppError> {
    require_perm(&actor, "delete").await?;
    role_svc::delete(&state.db, &role_id).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// PUT /{role_id} —— 部分更新角色(204; 不存在 404)
pub async fn update_role(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(role_id): Path<String>,
    AppJson(data): AppJson<RoleUpdate>,
) -> Result<StatusCode, AppError> {
    require_perm(&actor, "update").await?;
    role_svc::update(&state.db, &role_id, data).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// GET /name/{name} —— 按角色名称精确查询(不存在 404 "角色不存在")
pub async fn get_role_by_name(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(name): Path<String>,
) -> Result<Json<role::Model>, AppError> {
    require_perm(&actor, "read").await?;
    let role = role_svc::get_by_name(&state.db, &name).await?;
    Ok(Json(role))
}

/// GET /key/{role_key} —— 按权限字符串查询(不存在 404 "角色不存在")
pub async fn get_role_by_key(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(role_key): Path<String>,
) -> Result<Json<role::Model>, AppError> {
    require_perm(&actor, "read").await?;
    let role = role_svc::get_by_key(&state.db, &role_key).await?;
    Ok(Json(role))
}

/// 角色管理路由(挂载到 /authorization/roles)
pub fn router() -> axum::Router<common::runtime::AppState> {
    use axum::routing::{get, post};
    axum::Router::new()
        .route("/", post(create_role))
        .route("/list", get(list_roles))
        .route("/all", get(list_all_roles))
        .route("/name/{name}", get(get_role_by_name))
        .route("/key/{role_key}", get(get_role_by_key))
        .route(
            // 一级动态段统一命名 resource_id(axum merge 时不同名的同级动态段会冲突)
            "/{resource_id}",
            get(get_role).delete(delete_role).put(update_role),
        )
}
