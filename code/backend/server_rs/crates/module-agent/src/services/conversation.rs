//! 智能体对话列表服务(对齐 Python controller/agent_conversation.py)
//!
//! 创建/详情/更新/删除/消息列表由 RAG 侧的 /rag/conversations 系列接口提供,
//! 本模块仅补充智能体域的"我的会话"列表(复用 module_rag 的 conversation 表)。

use sea_orm::DatabaseConnection;

use common::utils::error::AppError;
use common::utils::pagination::{PaginationParams, PaginationResponse};

use module_rag::do_::entity::conversation;

use crate::dao::rag as rag_dao;

/// 分页获取当前用户的智能体对话(仅 agent_id 非空的会话; 可按智能体过滤, 更新时间倒序)
pub async fn list_my(
    db: &DatabaseConnection,
    user_id: &str,
    agent_id: Option<&str>,
    pagination: &PaginationParams,
) -> Result<PaginationResponse<conversation::Model>, AppError> {
    let items = rag_dao::list_agent_conversations(
        db,
        user_id,
        agent_id,
        pagination.offset(),
        pagination.limit(),
    )
    .await?;
    let total = rag_dao::count_agent_conversations(db, user_id, agent_id).await?;
    Ok(PaginationResponse::create(items, total, pagination))
}
