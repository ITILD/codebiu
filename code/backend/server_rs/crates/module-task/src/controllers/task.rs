//! 任务队列控制器(对齐 Python module_task/controller/task.py)
//!
//! 全部端点挂载于 /task/tasks 下(模块 router nest /tasks, 由 app 主入口 nest /task 前缀):
//! GET  /registry /stats /list /{task_id}
//! POST /            创建任务(201, 响应为任务ID字符串)
//! POST /{task_id}/sync /{task_id}/cancel(204) /{task_id}/retry
//! DELETE /{task_id}(204)
//!
//! 权限码 task:queue:{read,create,update,delete}; 错误契约: 裸 {"detail": 文案}。

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::pagination::PaginationParams;
use common::utils::extract::{AppJson, AppQuery};
use module_authorization::deps::{authorize, AuthUserId};
use serde::Deserialize;

use crate::do_::task::{check_max_len, TaskQueueCreateReq};
use crate::services::task::TaskQueueService;

/// 任务管理权限校验(task:queue:{act})
async fn require_perm(user: &AuthUserId, act: &str) -> Result<(), AppError> {
    authorize(&user.0, "task", "queue", act).await
}

/// /tasks/list 的过滤参数(与 Python Query 声明一致)
#[derive(Debug, Deserialize)]
struct ListQuery {
    /// 任务名称模糊搜索(≤200)
    keyword: Option<String>,
    /// 状态过滤(pending/running/success/failed/cancelled)
    status: Option<String>,
    /// 任务类型过滤
    task_type: Option<String>,
}

/// 任务路由(nest 到 /tasks 前缀)
pub fn router() -> Router<AppState> {
    Router::new()
        .route("/", post(create_task))
        .route("/registry", get(get_registry))
        .route("/stats", get(get_stats))
        .route("/list", get(list_tasks))
        .route("/{task_id}", get(get_task).delete(delete_task))
        .route("/{task_id}/sync", post(sync_task))
        .route("/{task_id}/cancel", post(cancel_task))
        .route("/{task_id}/retry", post(retry_task))
}

/// 创建任务并投递队列 — 201, 响应为任务ID字符串
async fn create_task(
    State(state): State<AppState>,
    user: AuthUserId,
    AppJson(req): AppJson<TaskQueueCreateReq>,
) -> Result<Response, AppError> {
    require_perm(&user, "create").await?;
    // 字段长度校验(对齐 pydantic max_length; 必填缺失由 serde → 422)
    check_max_len(&["body", "name"], &req.name, 200)?;
    check_max_len(&["body", "task_type"], &req.task_type, 50)?;
    let service = TaskQueueService::new(state);
    let id = service.create(req, &user.0).await?;
    Ok((StatusCode::CREATED, Json(id)).into_response())
}

/// 查询任务类型注册表(前端类型下拉/默认参数模板; 纯静态注册表无需数据库)
async fn get_registry(user: AuthUserId) -> Result<Response, AppError> {
    require_perm(&user, "read").await?;
    Ok(Json(TaskQueueService::registry()).into_response())
}

/// 按状态统计任务数(概览卡片, 供轮询刷新)
async fn get_stats(State(state): State<AppState>, user: AuthUserId) -> Result<Response, AppError> {
    require_perm(&user, "read").await?;
    let service = TaskQueueService::new(state);
    let stats = service.stats().await?;
    Ok(Json(stats).into_response())
}

/// 分页查询任务列表(列表项含状态/进度/失败原因/时间线)
async fn list_tasks(
    State(state): State<AppState>,
    user: AuthUserId,
    AppQuery(p): AppQuery<PaginationParams>,
    AppQuery(q): AppQuery<ListQuery>,
) -> Result<Response, AppError> {
    require_perm(&user, "read").await?;
    p.validate()?;
    if let Some(k) = &q.keyword {
        check_max_len(&["query", "keyword"], k, 200)?;
    }
    let service = TaskQueueService::new(state);
    let resp = service
        .list_page(
            &p,
            q.keyword.as_deref(),
            q.status.as_deref(),
            q.task_type.as_deref(),
        )
        .await?;
    Ok(Json(resp).into_response())
}

/// 查询任务详情(不存在 → 404, 文案与 Python 一致)
async fn get_task(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(task_id): Path<String>,
) -> Result<Response, AppError> {
    require_perm(&user, "read").await?;
    let service = TaskQueueService::new(state);
    let resp = service.get(&task_id).await?;
    Ok(Json(resp).into_response())
}

/// 从Celery同步任务状态(worker 回写中断时使用; Rust 无 celery 校正分支自然跳过)
async fn sync_task(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(task_id): Path<String>,
) -> Result<Response, AppError> {
    require_perm(&user, "update").await?;
    let service = TaskQueueService::new(state);
    let resp = service.sync_from_celery(&task_id).await?;
    Ok(Json(resp).into_response())
}

/// 取消任务 — 204(任务不存在 → 404, 已结束 → 400)
async fn cancel_task(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(task_id): Path<String>,
) -> Result<Response, AppError> {
    require_perm(&user, "update").await?;
    let service = TaskQueueService::new(state);
    service.cancel(&task_id).await?;
    Ok(StatusCode::NO_CONTENT.into_response())
}

/// 重试任务(重置进度后按引擎重新派发; 不存在 → 404, 进行中 → 400)
async fn retry_task(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(task_id): Path<String>,
) -> Result<Response, AppError> {
    require_perm(&user, "update").await?;
    let service = TaskQueueService::new(state);
    let resp = service.retry(&task_id).await?;
    Ok(Json(resp).into_response())
}

/// 删除任务记录(任何状态均可删除) — 204
async fn delete_task(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(task_id): Path<String>,
) -> Result<Response, AppError> {
    require_perm(&user, "delete").await?;
    let service = TaskQueueService::new(state);
    service.delete(&task_id).await?;
    Ok(StatusCode::NO_CONTENT.into_response())
}
