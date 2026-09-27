//! module-rag 会话/消息表复用读写(对齐 Python 侧复用 ConversationService/ChatMessageService)
//!
//! Python agent 模块直接注入 module_rag 的 service 读写 conversation/chat_message;
//! Rust 侧 module-rag 仅有实体层, 此处基于其实体实现 agent 域所需的最小读写子集:
//! - 会话列表(scope=agent: agent_id 非空, 可按智能体过滤, 更新时间倒序)
//! - 消息追加/列表/计数(流式对话持久化 + 历史上下文 + 自动标题)
//! - 会话读取/标题更新(自动标题回写)

use sea_orm::{
    ActiveModelTrait, ColumnTrait, DatabaseConnection, EntityTrait, PaginatorTrait, QueryFilter,
    QueryOrder, QuerySelect, Set,
};

use common::utils::error::AppError;

use module_rag::do_::entity::{chat_message, conversation, sea_orm_active_enums::Roletype};

/// 分页查询当前用户的智能体对话(仅 agent_id 非空的会话; 可按智能体过滤)
pub async fn list_agent_conversations(
    db: &DatabaseConnection,
    user_id: &str,
    agent_id: Option<&str>,
    offset: u64,
    limit: u64,
) -> Result<Vec<conversation::Model>, AppError> {
    let mut select = conversation::Entity::find()
        .filter(conversation::Column::UserId.eq(user_id))
        .filter(conversation::Column::AgentId.is_not_null())
        .order_by_desc(conversation::Column::UpdatedAt)
        .offset(offset)
        .limit(limit);
    if let Some(agent_id) = agent_id.filter(|s| !s.is_empty()) {
        select = select.filter(conversation::Column::AgentId.eq(agent_id));
    }
    Ok(select.all(db).await?)
}

/// 统计当前用户的智能体对话总数(口径与 list_agent_conversations 一致)
pub async fn count_agent_conversations(
    db: &DatabaseConnection,
    user_id: &str,
    agent_id: Option<&str>,
) -> Result<i64, AppError> {
    let mut select = conversation::Entity::find()
        .filter(conversation::Column::UserId.eq(user_id))
        .filter(conversation::Column::AgentId.is_not_null());
    if let Some(agent_id) = agent_id.filter(|s| !s.is_empty()) {
        select = select.filter(conversation::Column::AgentId.eq(agent_id));
    }
    Ok(select.count(db).await? as i64)
}

/// 查询单个会话(与 Python ConversationService.get 口径一致)
pub async fn conversation_get(
    db: &DatabaseConnection,
    conversation_id: &str,
) -> Result<Option<conversation::Model>, AppError> {
    Ok(conversation::Entity::find_by_id(conversation_id.to_owned())
        .one(db)
        .await?)
}

/// 更新会话标题(自动标题回写用)
pub async fn conversation_update_title(
    db: &DatabaseConnection,
    conversation_id: &str,
    title: &str,
) -> Result<(), AppError> {
    let Some(existing) = conversation_get(db, conversation_id).await? else {
        return Ok(());
    };
    let mut active: conversation::ActiveModel = existing.into();
    active.title = Set(title.to_string());
    active.update(db).await?;
    Ok(())
}

/// 新增聊天消息记录(主键 32 位 hex uuid, 对齐 Python ChatMessageDao.add)
pub async fn chat_message_add(
    db: &DatabaseConnection,
    conversation_id: &str,
    role: Roletype,
    content: &str,
    blocks: Option<serde_json::Value>,
) -> Result<String, AppError> {
    let id = crate::dao::agent::new_id();
    let active = chat_message::ActiveModel {
        id: Set(id.clone()),
        conversation_id: Set(conversation_id.to_string()),
        role: Set(role),
        content: Set(content.to_string()),
        blocks: Set(blocks),
        created_at: Set(Some(chrono::Utc::now().fixed_offset())),
    };
    active.insert(db).await?;
    Ok(id)
}

/// 按对话ID查询消息列表(按创建时间升序, 与 Python ChatMessageDao.list_by_conversation 一致)
pub async fn chat_message_list(
    db: &DatabaseConnection,
    conversation_id: &str,
    limit: u64,
) -> Result<Vec<chat_message::Model>, AppError> {
    Ok(chat_message::Entity::find()
        .filter(chat_message::Column::ConversationId.eq(conversation_id))
        .order_by_asc(chat_message::Column::CreatedAt)
        .limit(limit)
        .all(db)
        .await?)
}

/// 统计对话的消息总数(自动标题仅首轮触发用)
pub async fn chat_message_count(
    db: &DatabaseConnection,
    conversation_id: &str,
) -> Result<i64, AppError> {
    Ok(chat_message::Entity::find()
        .filter(chat_message::Column::ConversationId.eq(conversation_id))
        .count(db)
        .await? as i64)
}

/// 按用户ID查询模型绑定记录(流式对话解析对话模型用)
pub async fn user_model_get(
    db: &DatabaseConnection,
    user_id: &str,
) -> Result<Option<module_rag::do_::entity::user_model::Model>, AppError> {
    Ok(module_rag::do_::entity::user_model::Entity::find()
        .filter(module_rag::do_::entity::user_model::Column::UserId.eq(user_id))
        .one(db)
        .await?)
}

/// 查询用户所属部门ID(部门模型归属校验用, 对齐 Python UserDao.get 的部门读取)
pub async fn user_dept_id(
    db: &DatabaseConnection,
    user_id: &str,
) -> Result<Option<String>, AppError> {
    Ok(module_authorization::do_::entity::user::Entity::find_by_id(
        user_id.to_owned(),
    )
    .one(db)
    .await?
    .and_then(|u| u.dept_id))
}
