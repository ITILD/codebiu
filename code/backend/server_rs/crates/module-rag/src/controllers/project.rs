//! 项目/成员/部门授权控制器(对齐 Python module_rag/controller/project.py、
//! project_member.py、project_dept.py; 挂载前缀 /rag)

use axum::extract::{Path, Query, State};
use axum::http::StatusCode;
use axum::routing::{get, post, put};
use axum::{Json, Router};
use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::pagination::{PaginationParams, PaginationResponse};
use serde::Deserialize;

use module_authorization::deps::{authorize, AuthUserId};

use crate::do_::project::{
    validate_kb_category, ProjectCreate, ProjectDeptCreate, ProjectDeptResponse, ProjectDeptUpdate,
    ProjectDeptWithDept, ProjectMemberCreate, ProjectMemberResponse, ProjectMemberUpdate,
    ProjectMemberWithUser, ProjectResponse, MyProjectResponse,
};
use crate::services::permission::enforce_project_permission;
use crate::services::project as svc;

/// casbin 权限校验(rag 域, 对齐 Python require_permission)
async fn require_perm(user: &AuthUserId, obj: &str, act: &str) -> Result<(), AppError> {
    authorize(&user.0, "rag", obj, act).await
}

/// 内存分页(DAO 返回全量后切片, 对齐 Python service 层分页语义)
fn paginate<T>(items: Vec<T>, pagination: &PaginationParams) -> PaginationResponse<T> {
    let total = items.len() as i64;
    let page = items
        .into_iter()
        .skip(pagination.offset() as usize)
        .take(pagination.limit() as usize)
        .collect();
    PaginationResponse::create(page, total, pagination)
}

// ==================== query 参数载体 ====================

#[derive(Debug, Deserialize)]
struct ListQuery {
    #[serde(flatten)]
    pagination: PaginationParams,
    name: Option<String>,
    kb_category: Option<String>,
    is_private: Option<bool>,
}

#[derive(Debug, Deserialize)]
struct MemberListQuery {
    #[serde(flatten)]
    pagination: PaginationParams,
    role: Option<String>,
    user_keyword: Option<String>,
}

#[derive(Debug, Deserialize)]
struct DeptListQuery {
    #[serde(flatten)]
    pagination: PaginationParams,
    role: Option<String>,
}

// ==================== 项目管理(/rag/projects) ====================

/// 创建项目(201 返回项目ID; 权限码 rag:project:create)
async fn create_project(
    State(state): State<AppState>,
    user: AuthUserId,
    Json(req): Json<ProjectCreate>,
) -> Result<(StatusCode, Json<String>), AppError> {
    require_perm(&user, "project", "create").await?;
    let id = svc::project_add(&state, req, &user.0).await?;
    Ok((StatusCode::CREATED, Json(id)))
}

/// 分页查询项目列表(私有库仅授权人可见; admin 跳过可见性过滤)
async fn list_projects(
    State(state): State<AppState>,
    user: AuthUserId,
    Query(q): Query<ListQuery>,
) -> Result<Json<PaginationResponse<ProjectResponse>>, AppError> {
    require_perm(&user, "project", "read").await?;
    if let Some(c) = &q.kb_category {
        validate_kb_category(c).map_err(AppError::business)?;
    }
    // admin 跳过可见性过滤(viewer_id=None → 全量 + 权限位全 True)
    let viewer_id = if module_authorization::casbin_mgr::auth()
        .is_global_admin(&user.0)
        .await
    {
        None
    } else {
        Some(user.0.clone())
    };
    Ok(Json(
        svc::project_list_paged(&state, &q.pagination, q.kb_category, q.name, q.is_private, viewer_id)
            .await?,
    ))
}

/// 获取单个项目详情(含我的权限位)
async fn get_project(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(project_id): Path<String>,
) -> Result<Json<ProjectResponse>, AppError> {
    enforce_project_permission(&state, &user.0, &project_id, "project", "read").await?;
    svc::project_get_with_my_perms(&state, &project_id, &user.0)
        .await?
        .map(Json)
        .ok_or_else(|| AppError::not_found("项目未找到"))
}

/// 删除项目并级联清理(204)
async fn delete_project(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(project_id): Path<String>,
) -> Result<StatusCode, AppError> {
    enforce_project_permission(&state, &user.0, &project_id, "project", "delete").await?;
    svc::project_delete(&state, &project_id).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// 更新项目基础信息(204; is_private 变更需要 project_admin 档位)
async fn update_project(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(project_id): Path<String>,
    Json(req): Json<crate::do_::project::ProjectUpdate>,
) -> Result<StatusCode, AppError> {
    enforce_project_permission(&state, &user.0, &project_id, "project", "update").await?;
    svc::project_update(&state, &project_id, req, &user.0).await?;
    Ok(StatusCode::NO_CONTENT)
}

pub(crate) fn projects_router() -> Router<AppState> {
    Router::new()
        .route("/", post(create_project))
        .route("/list", get(list_projects))
        .route("/{project_id}", get(get_project).put(update_project).delete(delete_project))
}

// ==================== 项目成员(/rag/project-members) ====================

/// 添加项目成员(201 返回成员ID; 邀请档位 + 角色校验在服务层)
async fn add_project_member(
    State(state): State<AppState>,
    user: AuthUserId,
    Json(req): Json<ProjectMemberCreate>,
) -> Result<(StatusCode, Json<String>), AppError> {
    let id = svc::member_add(&state, req, &user.0).await?;
    Ok((StatusCode::CREATED, Json(id)))
}

/// 获取我参与的项目列表
async fn list_my_projects(
    State(state): State<AppState>,
    user: AuthUserId,
    Query(p): Query<PaginationParams>,
) -> Result<Json<PaginationResponse<MyProjectResponse>>, AppError> {
    p.validate()?;
    let items = svc::my_projects(&state, &user.0).await?;
    Ok(Json(paginate(items, &p)))
}

/// 获取项目成员列表(支持角色/用户关键字过滤)
async fn list_project_members(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(project_id): Path<String>,
    Query(q): Query<MemberListQuery>,
) -> Result<Json<PaginationResponse<ProjectMemberWithUser>>, AppError> {
    enforce_project_permission(&state, &user.0, &project_id, "member", "read").await?;
    let items = svc::member_list_by_project(&state, &project_id, q.role, q.user_keyword).await?;
    Ok(Json(paginate(items, &q.pagination)))
}

/// 获取单个项目成员详情(仅需登录, 对齐 Python)
async fn get_project_member(
    State(state): State<AppState>,
    _user: AuthUserId,
    Path(member_id): Path<String>,
) -> Result<Json<ProjectMemberResponse>, AppError> {
    Ok(Json(svc::member_get(&state, &member_id).await?))
}

/// 移除项目成员(204; 移除档位 + 管理员保底在服务层)
async fn remove_project_member(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(member_id): Path<String>,
) -> Result<StatusCode, AppError> {
    svc::member_delete(&state, &member_id, &user.0).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// 更新项目成员角色(204)
async fn update_project_member(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(member_id): Path<String>,
    Json(req): Json<ProjectMemberUpdate>,
) -> Result<StatusCode, AppError> {
    svc::member_update(&state, &member_id, req, &user.0).await?;
    Ok(StatusCode::NO_CONTENT)
}

pub(crate) fn members_router() -> Router<AppState> {
    Router::new()
        .route("/", post(add_project_member))
        .route("/my", get(list_my_projects))
        .route("/project/{project_id}", get(list_project_members))
        .route(
            "/{member_id}",
            get(get_project_member).put(update_project_member).delete(remove_project_member),
        )
}

// ==================== 项目部门授权(/rag/project-depts) ====================

/// 获取部门树(供项目授权选择, 仅需登录不要求 sys:dept:read)
async fn get_dept_tree_for_auth(
    State(state): State<AppState>,
    _user: AuthUserId,
) -> Result<Json<serde_json::Value>, AppError> {
    let tree = module_authorization::services::dept::get_tree(&state.db).await?;
    Ok(Json(serde_json::to_value(tree).unwrap_or(serde_json::Value::Null)))
}

/// 添加部门授权(201 返回授权记录ID; 复用成员 invite 档位)
async fn add_project_dept(
    State(state): State<AppState>,
    user: AuthUserId,
    Json(req): Json<ProjectDeptCreate>,
) -> Result<(StatusCode, Json<String>), AppError> {
    let id = svc::dept_add(&state, req, &user.0).await?;
    Ok((StatusCode::CREATED, Json(id)))
}

/// 获取项目部门授权列表(支持档位过滤)
async fn list_project_depts(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(project_id): Path<String>,
    Query(q): Query<DeptListQuery>,
) -> Result<Json<PaginationResponse<ProjectDeptWithDept>>, AppError> {
    enforce_project_permission(&state, &user.0, &project_id, "member", "read").await?;
    let items = svc::dept_list_by_project(&state, &project_id, q.role).await?;
    Ok(Json(paginate(items, &q.pagination)))
}

/// 更新部门授权档位(200 返回更新后的记录)
async fn update_project_dept(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(id): Path<String>,
    Json(req): Json<ProjectDeptUpdate>,
) -> Result<Json<ProjectDeptResponse>, AppError> {
    Ok(Json(svc::dept_update(&state, &id, req, &user.0).await?))
}

/// 移除部门授权(204)
async fn remove_project_dept(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(id): Path<String>,
) -> Result<StatusCode, AppError> {
    svc::dept_delete(&state, &id, &user.0).await?;
    Ok(StatusCode::NO_CONTENT)
}

pub(crate) fn depts_router() -> Router<AppState> {
    Router::new()
        .route("/dept-tree", get(get_dept_tree_for_auth))
        .route("/", post(add_project_dept))
        .route("/project/{project_id}", get(list_project_depts))
        .route(
            "/{id}",
            put(update_project_dept).delete(remove_project_dept),
        )
}
