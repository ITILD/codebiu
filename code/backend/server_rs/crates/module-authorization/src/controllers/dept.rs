//! 部门管理控制器(对齐 Python controller/dept.py)
//!
//! 路由前缀 /authorization/depts: CRUD + 树形结构。
//! 控制器只做请求解析/权限校验/响应包装, 业务规则(ancestors 计算/树形组装)
//! 与数据读写分别在 services/dao 层。

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::Json;

use crate::deps::{authorize, AuthUser};
use crate::do_::dept::{DeptCreate, DeptResponse, DeptTreeNode, DeptUpdate};
use crate::services::dept as dept_svc;
use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::extract::AppJson;
use crate::do_::entity::{dept, user};

/// sys:dept 资源权限校验
async fn require_perm(user: &user::Model, act: &str) -> Result<(), AppError> {
    authorize(&user.id, "sys", "dept", act).await
}

/// POST "" —— 创建部门(201; 父部门不存在 404, 重名 409)
pub async fn create_dept(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppJson(data): AppJson<DeptCreate>,
) -> Result<(StatusCode, Json<DeptResponse>), AppError> {
    require_perm(&actor, "create").await?;
    let created = dept_svc::create(&state.db, data).await?;
    Ok((StatusCode::CREATED, Json(DeptResponse::from(created))))
}

/// GET /tree —— 部门树形结构(各层按 order_num 升序, 孤儿节点提升为根)
pub async fn get_dept_tree(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
) -> Result<Json<Vec<DeptTreeNode>>, AppError> {
    require_perm(&actor, "read").await?;
    let tree = dept_svc::get_tree(&state.db).await?;
    Ok(Json(tree))
}

/// GET /list —— 全部部门扁平列表(按 order_num 升序)
pub async fn list_depts(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
) -> Result<Json<Vec<dept::Model>>, AppError> {
    require_perm(&actor, "read").await?;
    let items = dept_svc::list_all(&state.db).await?;
    Ok(Json(items))
}

/// GET /{dept_id} —— 获取单个部门(不存在 404)
pub async fn get_dept(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(dept_id): Path<String>,
) -> Result<Json<DeptResponse>, AppError> {
    require_perm(&actor, "read").await?;
    let d = dept_svc::get(&state.db, &dept_id).await?;
    Ok(Json(DeptResponse::from(d)))
}

/// DELETE /{dept_id} —— 删除部门(存在子部门 400; 不存在 404; 不做级联删除)
pub async fn delete_dept(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(dept_id): Path<String>,
) -> Result<StatusCode, AppError> {
    require_perm(&actor, "delete").await?;
    dept_svc::delete(&state.db, &dept_id).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// PUT /{dept_id} —— 部分更新部门(调整 parent_id 时自动重算 ancestors; 不存在 404)
pub async fn update_dept(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(dept_id): Path<String>,
    AppJson(data): AppJson<DeptUpdate>,
) -> Result<StatusCode, AppError> {
    require_perm(&actor, "update").await?;
    dept_svc::update(&state.db, &dept_id, data).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// 部门管理路由(挂载到 /authorization/depts)
pub fn router() -> axum::Router<common::runtime::AppState> {
    use axum::routing::{get, post};
    axum::Router::new()
        .route("/", post(create_dept))
        .route("/tree", get(get_dept_tree))
        .route("/list", get(list_depts))
        .route(
            // 一级动态段统一命名 resource_id(axum merge 时不同名的同级动态段会冲突)
            "/{resource_id}",
            get(get_dept).delete(delete_dept).put(update_dept),
        )
}
