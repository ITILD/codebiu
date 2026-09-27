//! 异步并发示例控制器(对齐 Python module_template/controller/template_async_learn.py)
//!
//! 四种执行模式的 Rust 等价:
//! - sync            同步任务丢入阻塞线程池(spawn_blocking), 不阻塞异步执行器
//! - async           await tokio::time::sleep 挂起, 期间执行器可处理其他请求
//! - async-sync      反例: 在异步执行器内直接调用阻塞任务(会卡住当前 worker)
//! - async-threadpool 推荐模式: 异步路由经 spawn_blocking 运行同步任务

use std::time::{Duration, Instant};

use axum::extract::Path;
use axum::routing::get;
use axum::{Json, Router};
use module_authorization::do_::entity::user;
use module_authorization::deps::{authorize, AuthUser};

use common::utils::error::AppError;

/// template:async_learn 资源权限校验
async fn require_perm(user: &user::Model, act: &str) -> Result<(), AppError> {
    authorize(&user.id, "template", "async_learn", act).await
}

/// 模拟同步耗时任务(阻塞当前线程)
fn sync_heavy_task(task_id: &str, duration: f64) -> String {
    tracing::info!("[Sync-Heavy-Task] {task_id} start");
    std::thread::sleep(Duration::from_secs_f64(duration));
    tracing::info!("[Sync-Heavy-Task] {task_id} done");
    format!("Sync task {task_id} completed")
}

/// GET /sync/{id}/{duration_use} —— 同步耗时任务(丢入阻塞线程池, 不阻塞异步执行器)
pub async fn sync_endpoint(
    AuthUser(actor): AuthUser,
    Path((id, duration_use)): Path<(String, f64)>,
) -> Result<Json<serde_json::Value>, AppError> {
    require_perm(&actor, "read").await?;
    tracing::info!("[Sync] {id} start");
    let start = Instant::now();
    let task_id = id.clone();
    let result = tokio::task::spawn_blocking(move || sync_heavy_task(&task_id, duration_use))
        .await
        .map_err(|e| AppError::Internal(format!("任务执行失败: {e}")))?;
    tracing::info!("[Sync] {id} done in {:.2}s", start.elapsed().as_secs_f64());
    Ok(Json(serde_json::json!({ "id": id, "result": result })))
}

/// GET /async/{id}/{duration_use} —— 异步耗时任务(await 挂起, 不阻塞执行器)
pub async fn async_endpoint(
    AuthUser(actor): AuthUser,
    Path((id, duration_use)): Path<(String, f64)>,
) -> Result<Json<serde_json::Value>, AppError> {
    require_perm(&actor, "read").await?;
    tracing::info!("[Async] {id} start");
    let start = Instant::now();
    tokio::time::sleep(Duration::from_secs_f64(duration_use)).await;
    tracing::info!("[Async] {id} done in {:.2}s", start.elapsed().as_secs_f64());
    Ok(Json(
        serde_json::json!({ "id": id, "result": format!("Async task {id} completed") }),
    ))
}

/// GET /async-sync/{id}/{duration_use} —— 反例: 异步执行器内直接调用同步任务(阻塞执行器)
pub async fn async_sync_endpoint(
    AuthUser(actor): AuthUser,
    Path((id, duration_use)): Path<(String, f64)>,
) -> Result<Json<serde_json::Value>, AppError> {
    require_perm(&actor, "read").await?;
    tracing::info!("[Async-Sync] {id} start");
    let start = Instant::now();
    let result = sync_heavy_task(&id, duration_use);
    tracing::info!(
        "[Async-Sync] {id} done in {:.2}s",
        start.elapsed().as_secs_f64()
    );
    Ok(Json(serde_json::json!({ "id": id, "result": result })))
}

/// GET /async-threadpool/{id}/{duration_use} —— 异步路由经线程池运行同步任务(推荐)
pub async fn async_threadpool_endpoint(
    AuthUser(actor): AuthUser,
    Path((id, duration_use)): Path<(String, f64)>,
) -> Result<Json<serde_json::Value>, AppError> {
    require_perm(&actor, "read").await?;
    tracing::info!("[Async-Threadpool] {id} start");
    let start = Instant::now();
    let task_id = id.clone();
    let result = tokio::task::spawn_blocking(move || sync_heavy_task(&task_id, duration_use))
        .await
        .map_err(|e| AppError::Internal(format!("任务执行失败: {e}")))?;
    tracing::info!(
        "[Async-Threadpool] {id} done in {:.2}s",
        start.elapsed().as_secs_f64()
    );
    Ok(Json(serde_json::json!({ "id": id, "result": result })))
}

/// 异步示例子路由(nest 到 /template/template-async-learn 前缀)
pub fn router() -> Router<common::runtime::AppState> {
    Router::new()
        .route("/sync/{id}/{duration_use}", get(sync_endpoint))
        .route("/async/{id}/{duration_use}", get(async_endpoint))
        .route("/async-sync/{id}/{duration_use}", get(async_sync_endpoint))
        .route(
            "/async-threadpool/{id}/{duration_use}",
            get(async_threadpool_endpoint),
        )
}
