//! 权限管理控制器(对齐 Python controller/permission.py)
//!
//! 路由前缀 /authorization/permissions: CRUD + 分页列表 + 树形结构 + 按代码/父级查询。
//! 控制器只做请求解析/权限校验/响应包装, 业务规则(树形组装)与数据读写
//! 分别在 services/dao 层。

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::Json;

use crate::deps::{authorize, AuthUser};
use crate::do_::permission::{PermissionCreate, PermissionTreeNode, PermissionUpdate};
use crate::services::permission as permission_svc;
use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::extract::{AppJson, AppQuery};
use common::utils::pagination::{PaginationParams, PaginationResponse};
use crate::do_::entity::{permission, user};

/// sys:permission 资源权限校验
async fn require_perm(user: &user::Model, act: &str) -> Result<(), AppError> {
    authorize(&user.id, "sys", "permission", act).await
}

/// POST "" —— 创建权限(201; 返回权限ID)
pub async fn create_permission(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppJson(data): AppJson<PermissionCreate>,
) -> Result<(StatusCode, Json<String>), AppError> {
    require_perm(&actor, "create").await?;
    let created = permission_svc::create(&state.db, data).await?;
    Ok((StatusCode::CREATED, Json(created.id)))
}

/// GET /tree —— 权限/菜单树形结构(各层按 order_num 升序)
pub async fn get_permission_tree(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
) -> Result<Json<Vec<PermissionTreeNode>>, AppError> {
    require_perm(&actor, "read").await?;
    let tree = permission_svc::get_tree(&state.db).await?;
    Ok(Json(tree))
}

/// GET /list —— 分页查询权限列表(无过滤参数, total 为权限总数; 与 Python 一致无排序)
pub async fn list_permissions(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppQuery(pagination): AppQuery<PaginationParams>,
) -> Result<Json<PaginationResponse<permission::Model>>, AppError> {
    require_perm(&actor, "read").await?;
    pagination.validate()?;
    let page = permission_svc::list_paged(&state.db, &pagination).await?;
    Ok(Json(page))
}

/// GET /code/{code} —— 按权限代码精确查询(不存在 404 "权限不存在")
pub async fn get_permission_by_code(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(code): Path<String>,
) -> Result<Json<permission::Model>, AppError> {
    require_perm(&actor, "read").await?;
    let perm = permission_svc::get_by_code(&state.db, &code).await?;
    Ok(Json(perm))
}

/// GET /parent/{parent_id} —— 指定父权限下的子权限列表(按 order_num 升序)
pub async fn get_permissions_by_parent(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(parent_id): Path<String>,
) -> Result<Json<Vec<permission::Model>>, AppError> {
    require_perm(&actor, "read").await?;
    let items = permission_svc::list_by_parent(&state.db, &parent_id).await?;
    Ok(Json(items))
}

/// GET /{permission_id} —— 获取单个权限(不存在 404 "权限不存在")
pub async fn get_permission(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(permission_id): Path<String>,
) -> Result<Json<permission::Model>, AppError> {
    require_perm(&actor, "read").await?;
    let perm = permission_svc::get(&state.db, &permission_id).await?;
    Ok(Json(perm))
}

/// DELETE /{permission_id} —— 删除权限(204; 不存在 404; 不做子权限级联校验)
pub async fn delete_permission(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(permission_id): Path<String>,
) -> Result<StatusCode, AppError> {
    require_perm(&actor, "delete").await?;
    permission_svc::delete(&state.db, &permission_id).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// PUT /{permission_id} —— 部分更新权限(204; 不存在 404)
pub async fn update_permission(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(permission_id): Path<String>,
    AppJson(data): AppJson<PermissionUpdate>,
) -> Result<StatusCode, AppError> {
    require_perm(&actor, "update").await?;
    permission_svc::update(&state.db, &permission_id, data).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// 权限管理路由(挂载到 /authorization/permissions)
pub fn router() -> axum::Router<common::runtime::AppState> {
    use axum::routing::{get, post};
    axum::Router::new()
        .route("/", post(create_permission))
        .route("/tree", get(get_permission_tree))
        .route("/list", get(list_permissions))
        .route("/code/{code}", get(get_permission_by_code))
        .route("/parent/{parent_id}", get(get_permissions_by_parent))
        .route(
            // 一级动态段统一命名 resource_id(axum merge 时不同名的同级动态段会冲突)
            "/{resource_id}",
            get(get_permission)
                .delete(delete_permission)
                .put(update_permission),
        )
}
