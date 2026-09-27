//! 智能体管理控制器(对齐 Python controller/agent.py; 与 agent_run 共用 /agents 前缀)
//!
//! - GET / POST "" : 列表与创建
//! - GET / PUT / DELETE "/{agent_id}" : 详情/更新/删除
//! - PUT "/{agent_id}/workflow" : 保存工作流配置

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::routing::{get, put};
use axum::{Json, Router};

use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::extract::{AppJson, AppQuery};
use common::utils::pagination::{PaginationParams, PaginationResponse};
use module_authorization::deps::{authorize, AuthUser};

use crate::do_::agent::{AgentCreate, AgentResp, AgentUpdate, AgentWorkflowSaveRequest};
use crate::services::agent as svc;

/// GET "" —— 分页获取当前用户可访问的智能体(公共+本人, 内置优先)
pub async fn list_agents(
    State(state): State<AppState>,
    AppQuery(pagination): AppQuery<PaginationParams>,
    AuthUser(current_user): AuthUser,
) -> Result<Json<PaginationResponse<AgentResp>>, AppError> {
    pagination.validate()?;
    authorize(&current_user.id, "agent", "manage", "read").await?;
    Ok(Json(
        svc::list_accessible(&state.db, &current_user.id, &pagination).await?,
    ))
}

/// GET "/{agent_id}" —— 智能体详情(不存在返回 404, 文案对齐 Python)
pub async fn get_agent(
    State(state): State<AppState>,
    Path(agent_id): Path<String>,
    AuthUser(current_user): AuthUser,
) -> Result<Json<AgentResp>, AppError> {
    authorize(&current_user.id, "agent", "manage", "read").await?;
    svc::get(&state.db, &agent_id)
        .await?
        .map(Json)
        .ok_or_else(|| AppError::not_found("智能体未找到"))
}

/// POST "" —— 创建自定义智能体(私有, 201 返回新ID)
pub async fn create_agent(
    State(state): State<AppState>,
    AuthUser(current_user): AuthUser,
    AppJson(data): AppJson<AgentCreate>,
) -> Result<(StatusCode, Json<String>), AppError> {
    authorize(&current_user.id, "agent", "manage", "create").await?;
    data.validate()?;
    Ok((
        StatusCode::CREATED,
        Json(svc::create(&state.db, &current_user.id, &data).await?),
    ))
}

/// PUT "/{agent_id}" —— 更新智能体(仅创建者或管理员; 204)
pub async fn update_agent(
    State(state): State<AppState>,
    Path(agent_id): Path<String>,
    AuthUser(current_user): AuthUser,
    AppJson(data): AppJson<AgentUpdate>,
) -> Result<StatusCode, AppError> {
    authorize(&current_user.id, "agent", "manage", "update").await?;
    data.validate()?;
    svc::update(&state.db, &agent_id, &current_user.id, &data).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// PUT "/{agent_id}/workflow" —— 保存工作流配置(校验通过才落库; 204)
pub async fn save_agent_workflow(
    State(state): State<AppState>,
    Path(agent_id): Path<String>,
    AuthUser(current_user): AuthUser,
    AppJson(data): AppJson<AgentWorkflowSaveRequest>,
) -> Result<StatusCode, AppError> {
    authorize(&current_user.id, "agent", "manage", "update").await?;
    svc::save_workflow(&state.db, &agent_id, &current_user.id, &data).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// DELETE "/{agent_id}" —— 删除智能体(仅创建者或管理员, 内置不可删; 204)
pub async fn delete_agent(
    State(state): State<AppState>,
    Path(agent_id): Path<String>,
    AuthUser(current_user): AuthUser,
) -> Result<StatusCode, AppError> {
    authorize(&current_user.id, "agent", "manage", "delete").await?;
    svc::delete(&state.db, &agent_id, &current_user.id).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// 智能体管理子路由(nest 到 /agents 前缀)
pub fn router() -> Router<AppState> {
    Router::new()
        .route("/", get(list_agents).post(create_agent))
        .route(
            "/{agent_id}",
            get(get_agent).put(update_agent).delete(delete_agent),
        )
        .route("/{agent_id}/workflow", put(save_agent_workflow))
}
