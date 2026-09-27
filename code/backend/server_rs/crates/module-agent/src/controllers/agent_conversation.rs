//! 智能体对话管理控制器(对齐 Python controller/agent_conversation.py)
//!
//! 创建/详情/更新/删除/消息列表直接复用 /rag/conversations 系列接口;
//! 本控制器仅补充智能体域的会话列表(复用 module_rag 的 conversation 表)。

use axum::extract::State;
use axum::routing::get;
use axum::{Json, Router};
use serde::Deserialize;

use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::extract::AppQuery;
use common::utils::pagination::{PaginationParams, PaginationResponse};
use module_authorization::deps::{authorize, AuthUser};
use module_rag::do_::entity::conversation;

use crate::services::conversation as svc;

/// GET /my 查询参数(可选按智能体过滤)
#[derive(Debug, Deserialize)]
pub struct AgentIdQuery {
    #[serde(default)]
    pub agent_id: Option<String>,
}

/// GET "/my" —— 分页获取当前用户的智能体对话(仅 agent_id 非空的会话; 可按智能体过滤)
pub async fn list_my_conversations(
    State(state): State<AppState>,
    AppQuery(pagination): AppQuery<PaginationParams>,
    AppQuery(query): AppQuery<AgentIdQuery>,
    AuthUser(current_user): AuthUser,
) -> Result<Json<PaginationResponse<conversation::Model>>, AppError> {
    pagination.validate()?;
    authorize(&current_user.id, "agent", "chat", "read").await?;
    Ok(Json(
        svc::list_my(
            &state.db,
            &current_user.id,
            query.agent_id.as_deref(),
            &pagination,
        )
        .await?,
    ))
}

/// 智能体对话管理子路由(nest 到 /conversations 前缀)
pub fn router() -> Router<AppState> {
    Router::new().route("/my", get(list_my_conversations))
}
