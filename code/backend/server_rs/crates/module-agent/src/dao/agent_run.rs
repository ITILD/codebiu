//! 智能体运行历史数据访问(对齐 Python module_agent/dao/agent_run.py)

use sea_orm::{
    ActiveModelTrait, ColumnTrait, DatabaseConnection, EntityTrait, PaginatorTrait, QueryFilter,
    QueryOrder, QuerySelect, Set,
};

use crate::do_::entity::agent_run;

/// 运行记录落库参数
pub struct RunNew {
    pub id: String,
    pub agent_id: String,
    pub user_id: String,
    pub model_id: String,
    pub input: serde_json::Value,
    pub output: serde_json::Value,
    pub trace: Option<serde_json::Value>,
}

/// 新增运行历史记录(输入/输出统一以 JSON 存储, 字符串存为 JSON 标量)
pub async fn add(db: &DatabaseConnection, run: RunNew) -> Result<String, AppErr> {
    let id = run.id.clone();
    let active = agent_run::ActiveModel {
        id: Set(run.id),
        agent_id: Set(run.agent_id),
        user_id: Set(run.user_id),
        model_id: Set(run.model_id),
        input: Set(run.input),
        output: Set(run.output),
        trace: Set(run.trace),
        created_at: Set(Some(chrono::Utc::now().fixed_offset())),
    };
    active.insert(db).await?;
    Ok(id)
}

/// 按ID查询单条运行记录(仅本人)
pub async fn get_run(
    db: &DatabaseConnection,
    run_id: &str,
    user_id: &str,
) -> Result<Option<agent_run::Model>, AppErr> {
    Ok(agent_run::Entity::find()
        .filter(agent_run::Column::Id.eq(run_id))
        .filter(agent_run::Column::UserId.eq(user_id))
        .one(db)
        .await?)
}

/// 分页查询某用户在指定智能体下的运行历史(按运行时间倒序)
pub async fn list_by_agent_user(
    db: &DatabaseConnection,
    agent_id: &str,
    user_id: &str,
    offset: u64,
    limit: u64,
) -> Result<Vec<agent_run::Model>, AppErr> {
    Ok(agent_run::Entity::find()
        .filter(agent_run::Column::AgentId.eq(agent_id))
        .filter(agent_run::Column::UserId.eq(user_id))
        .order_by_desc(agent_run::Column::CreatedAt)
        .offset(offset)
        .limit(limit)
        .all(db)
        .await?)
}

/// 统计某用户在指定智能体下的运行历史总数
pub async fn count_by_agent_user(
    db: &DatabaseConnection,
    agent_id: &str,
    user_id: &str,
) -> Result<i64, AppErr> {
    Ok(agent_run::Entity::find()
        .filter(agent_run::Column::AgentId.eq(agent_id))
        .filter(agent_run::Column::UserId.eq(user_id))
        .count(db)
        .await? as i64)
}

/// 模块内 Result 别名
type AppErr = common::utils::error::AppError;
