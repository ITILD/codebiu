//! 智能体数据访问(对齐 Python module_agent/dao/agent.py)

use sea_orm::{
    ActiveModelTrait, ColumnTrait, Condition, DatabaseConnection, EntityTrait, PaginatorTrait,
    QueryFilter, QueryOrder, QuerySelect, Set,
};
use uuid::Uuid;

use common::utils::error::AppError;

use crate::do_::agent::{AgentNew, AgentUpdate};
use crate::do_::entity::agent;

/// 新增智能体记录(主键为 32 位小写 hex uuid, 与 Python uuid4().hex 一致)
///
/// :param new: 落库参数(含预设 id 供内置种子幂等写入)
pub async fn add(db: &DatabaseConnection, new: AgentNew) -> Result<String, AppError> {
    let now = chrono::Utc::now().fixed_offset();
    let id = new.id.clone();
    let active = agent::ActiveModel {
        id: Set(new.id),
        name: Set(new.name),
        description: Set(new.description),
        system_prompt: Set(new.system_prompt),
        agent_type: Set(new.agent_type.as_str().to_string()),
        workflow: Set(new.workflow),
        input_type: Set(new.input_type.as_str().to_string()),
        output_type: Set(new.output_type.as_str().to_string()),
        input_schema: Set(new.input_schema),
        output_schema: Set(new.output_schema),
        is_public: Set(new.is_public),
        is_builtin: Set(new.is_builtin),
        created_by: Set(new.created_by),
        created_at: Set(Some(now)),
        updated_at: Set(now),
    };
    active.insert(db).await?;
    Ok(id)
}

/// 按ID查询智能体(与 Python session.get 口径一致, 不过滤可见性)
pub async fn get(db: &DatabaseConnection, agent_id: &str) -> Result<Option<agent::Model>, AppError> {
    Ok(agent::Entity::find_by_id(agent_id.to_owned())
        .one(db)
        .await?)
}

/// 部分更新智能体(仅显式传入字段生效, 同步刷新 updated_at)
///
/// :raises: AppError::not_found 智能体不存在(文案对齐 Python)
pub async fn update(
    db: &DatabaseConnection,
    agent_id: &str,
    patch: &AgentUpdate,
) -> Result<(), AppError> {
    let Some(existing) = get(db, agent_id).await? else {
        return Err(AppError::not_found(format!("未找到ID为 {agent_id} 的智能体")));
    };
    let mut active: agent::ActiveModel = existing.into();
    if let Some(v) = &patch.name {
        active.name = Set(v.clone());
    }
    if let Some(v) = &patch.description {
        active.description = Set(v.clone());
    }
    if let Some(v) = &patch.system_prompt {
        active.system_prompt = Set(v.clone());
    }
    if let Some(v) = patch.agent_type {
        active.agent_type = Set(v.as_str().to_string());
    }
    if let Some(v) = &patch.workflow {
        active.workflow = Set(Some(v.clone()));
    } else if patch.clear_workflow {
        active.workflow = Set(None);
    }
    if let Some(v) = patch.input_type {
        active.input_type = Set(v.as_str().to_string());
    }
    if let Some(v) = patch.output_type {
        active.output_type = Set(v.as_str().to_string());
    }
    if let Some(v) = &patch.input_schema {
        active.input_schema = Set(Some(v.clone()));
    }
    if let Some(v) = &patch.output_schema {
        active.output_schema = Set(Some(v.clone()));
    }
    // 对齐 SQLModel Column(onupdate): 更新时自动刷新 updated_at
    active.updated_at = Set(chrono::Utc::now().fixed_offset());
    active.update(db).await?;
    Ok(())
}

/// 删除指定智能体
///
/// :raises: AppError::not_found 智能体不存在(文案对齐 Python)
pub async fn delete(db: &DatabaseConnection, agent_id: &str) -> Result<(), AppError> {
    let res = agent::Entity::delete_by_id(agent_id.to_owned())
        .exec(db)
        .await?;
    if res.rows_affected == 0 {
        return Err(AppError::not_found(format!("未找到ID为 {agent_id} 的智能体")));
    }
    Ok(())
}

/// 查询用户可访问的智能体(公共 或 本人创建, 内置优先, 更新时间倒序)
pub async fn list_accessible(
    db: &DatabaseConnection,
    user_id: &str,
    offset: u64,
    limit: u64,
) -> Result<Vec<agent::Model>, AppError> {
    Ok(agent::Entity::find()
        .filter(
            Condition::any()
                .add(agent::Column::IsPublic.eq(true))
                .add(agent::Column::CreatedBy.eq(user_id)),
        )
        .order_by_desc(agent::Column::IsBuiltin)
        .order_by_desc(agent::Column::UpdatedAt)
        .offset(offset)
        .limit(limit)
        .all(db)
        .await?)
}

/// 统计用户可访问的智能体总数
pub async fn count_accessible(db: &DatabaseConnection, user_id: &str) -> Result<i64, AppError> {
    Ok(agent::Entity::find()
        .filter(
            Condition::any()
                .add(agent::Column::IsPublic.eq(true))
                .add(agent::Column::CreatedBy.eq(user_id)),
        )
        .count(db)
        .await? as i64)
}

/// 按ID列表批量查询(种子幂等写入用)
pub async fn list_by_ids(
    db: &DatabaseConnection,
    agent_ids: &[String],
) -> Result<Vec<agent::Model>, AppError> {
    if agent_ids.is_empty() {
        return Ok(vec![]);
    }
    Ok(agent::Entity::find()
        .filter(agent::Column::Id.is_in(agent_ids.to_vec()))
        .all(db)
        .await?)
}

/// 生成 32 位 hex uuid(对齐 Python uuid4().hex)
pub fn new_id() -> String {
    Uuid::new_v4().simple().to_string()
}
