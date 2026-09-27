//! 对话/消息 DAO(对齐 Python module_rag/dao/conversation.py、chat_message.py)

use sea_orm::{
    ActiveModelTrait, ColumnTrait, Condition, DatabaseConnection, DbErr, EntityTrait,
    IntoActiveModel, PaginatorTrait, QueryFilter, QueryOrder, QuerySelect, Set,
};

use crate::do_::entity::{chat_message, conversation};
use crate::do_::entity::sea_orm_active_enums::Roletype;

// ==================== 对话 ====================

/// 新增对话
pub async fn conversation_add(
    db: &DatabaseConnection,
    am: conversation::ActiveModel,
) -> Result<conversation::Model, DbErr> {
    am.insert(db).await
}

/// 按ID获取对话
pub async fn conversation_get(
    db: &DatabaseConnection,
    id: &str,
) -> Result<Option<conversation::Model>, DbErr> {
    conversation::Entity::find_by_id(id.to_owned()).one(db).await
}

/// 更新对话(仅 Some 字段)
pub async fn conversation_update(
    db: &DatabaseConnection,
    model: conversation::Model,
    title: Option<String>,
    agent_id: Option<Option<String>>,
    project_ids: Option<Vec<String>>,
) -> Result<conversation::Model, DbErr> {
    let mut am = model.into_active_model();
    if let Some(v) = title {
        am.title = Set(v);
    }
    if let Some(v) = agent_id {
        am.agent_id = Set(v);
    }
    if let Some(v) = project_ids {
        am.project_ids = Set(crate::do_::chat::string_vec_to_json(&v));
    }
    am.updated_at = Set(chrono::Utc::now().into());
    am.update(db).await
}

/// 删除对话
pub async fn conversation_delete(db: &DatabaseConnection, id: &str) -> Result<(), DbErr> {
    conversation::Entity::delete_by_id(id.to_owned()).exec(db).await?;
    Ok(())
}

/// 用户对话分页列表(scope: all=全部 / rag=知识库对话(agent_id 为空) / agent=智能体对话)
pub async fn conversation_list_by_user(
    db: &DatabaseConnection,
    user_id: &str,
    scope: &str,
    offset: u64,
    limit: u64,
) -> Result<Vec<conversation::Model>, DbErr> {
    let mut cond = Condition::all().add(conversation::Column::UserId.eq(user_id));
    match scope {
        "rag" => cond = cond.add(conversation::Column::AgentId.is_null()),
        "agent" => cond = cond.add(conversation::Column::AgentId.is_not_null()),
        _ => {}
    }
    conversation::Entity::find()
        .filter(cond)
        .order_by_desc(conversation::Column::UpdatedAt)
        .offset(offset)
        .limit(limit)
        .all(db)
        .await
}

/// 用户对话计数(scope 口径同列表)
pub async fn conversation_count_by_user(
    db: &DatabaseConnection,
    user_id: &str,
    scope: &str,
) -> Result<i64, DbErr> {
    let mut cond = Condition::all().add(conversation::Column::UserId.eq(user_id));
    match scope {
        "rag" => cond = cond.add(conversation::Column::AgentId.is_null()),
        "agent" => cond = cond.add(conversation::Column::AgentId.is_not_null()),
        _ => {}
    }
    conversation::Entity::find().filter(cond).count(db).await.map(|c| c as i64)
}

// ==================== 聊天消息 ====================

/// 新增消息
pub async fn message_add(
    db: &DatabaseConnection,
    am: chat_message::ActiveModel,
) -> Result<chat_message::Model, DbErr> {
    am.insert(db).await
}

/// 对话消息列表(按创建时间升序)
pub async fn message_list_by_conversation(
    db: &DatabaseConnection,
    conversation_id: &str,
) -> Result<Vec<chat_message::Model>, DbErr> {
    chat_message::Entity::find()
        .filter(chat_message::Column::ConversationId.eq(conversation_id))
        .order_by_asc(chat_message::Column::CreatedAt)
        .all(db)
        .await
}

/// 对话消息计数
pub async fn message_count_by_conversation(
    db: &DatabaseConnection,
    conversation_id: &str,
) -> Result<i64, DbErr> {
    chat_message::Entity::find()
        .filter(chat_message::Column::ConversationId.eq(conversation_id))
        .count(db)
        .await
        .map(|c| c as i64)
}

/// 删除对话全部消息(对话级联删除)
pub async fn message_delete_by_conversation(
    db: &DatabaseConnection,
    conversation_id: &str,
) -> Result<(), DbErr> {
    chat_message::Entity::delete_many()
        .filter(chat_message::Column::ConversationId.eq(conversation_id))
        .exec(db)
        .await?;
    Ok(())
}

/// 对话最近 N 条历史消息(按时间升序返回; 问答上下文构建用)
pub async fn message_list_recent(
    db: &DatabaseConnection,
    conversation_id: &str,
    limit: u64,
) -> Result<Vec<chat_message::Model>, DbErr> {
    let mut rows = chat_message::Entity::find()
        .filter(chat_message::Column::ConversationId.eq(conversation_id))
        .order_by_desc(chat_message::Column::CreatedAt)
        .limit(limit)
        .all(db)
        .await?;
    rows.reverse();
    Ok(rows)
}

/// 消息角色枚举 → 字符串(响应序列化用)
pub fn role_str(role: &Roletype) -> &'static str {
    match role {
        Roletype::System => "system",
        Roletype::User => "user",
        Roletype::Assistant => "assistant",
    }
}
