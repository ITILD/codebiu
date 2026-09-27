//! 智能体运行控制器(对齐 Python controller/agent_run.py; 与管理端点共用 /agents 前缀)
//!
//! - POST "/{agent_id}/run" : 结构化输入输出的一次性运行(真实 LLM/工作流调用)
//! - GET "/{agent_id}/runs" : 运行历史分页(仅本人)
//! - GET "/{agent_id}/runs/{run_id}" : 运行详情(含工作流节点轨迹)

use axum::extract::{Path, State};
use axum::routing::{get, post};
use axum::{Json, Router};

use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::extract::{AppJson, AppQuery};
use common::utils::pagination::{PaginationParams, PaginationResponse};
use module_authorization::deps::{authorize, AuthUser};

use crate::do_::agent_run::{AgentRunHistory, AgentRunRequest, AgentRunResponse};
use crate::services::agent_run as svc;

/// POST "/{agent_id}/run" —— 运行智能体(仅公共或本人创建可运行, 成功写入运行历史)
pub async fn run_agent(
    State(state): State<AppState>,
    Path(agent_id): Path<String>,
    AuthUser(current_user): AuthUser,
    AppJson(request): AppJson<AgentRunRequest>,
) -> Result<Json<AgentRunResponse>, AppError> {
    authorize(&current_user.id, "agent", "chat", "write").await?;
    Ok(Json(svc::run(&state, &agent_id, &current_user.id, &request).await?))
}

/// GET "/{agent_id}/runs" —— 分页返回当前用户在指定智能体下的运行记录(按时间倒序)
pub async fn list_agent_runs(
    State(state): State<AppState>,
    Path(agent_id): Path<String>,
    AppQuery(pagination): AppQuery<PaginationParams>,
    AuthUser(current_user): AuthUser,
) -> Result<Json<PaginationResponse<AgentRunHistory>>, AppError> {
    pagination.validate()?;
    authorize(&current_user.id, "agent", "chat", "read").await?;
    Ok(Json(
        svc::list_runs(&state.db, &agent_id, &current_user.id, &pagination).await?,
    ))
}

/// GET "/{agent_id}/runs/{run_id}" —— 运行详情(含工作流节点轨迹, 仅本人记录)
pub async fn get_agent_run_detail(
    State(state): State<AppState>,
    Path((agent_id, run_id)): Path<(String, String)>,
    AuthUser(current_user): AuthUser,
) -> Result<Json<AgentRunHistory>, AppError> {
    authorize(&current_user.id, "agent", "chat", "read").await?;
    Ok(Json(
        svc::get_run_detail(&state.db, &agent_id, &run_id, &current_user.id).await?,
    ))
}

/// 智能体运行子路由(nest 到 /agents 前缀, 与管理控制器 merge)
pub fn router() -> Router<AppState> {
    Router::new()
        .route("/{agent_id}/run", post(run_agent))
        .route("/{agent_id}/runs", get(list_agent_runs))
        .route("/{agent_id}/runs/{run_id}", get(get_agent_run_detail))
}
