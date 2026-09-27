//! 智能体管理服务(对齐 Python module_agent/service/agent.py)
//!
//! 职责: CRUD + 归属校验(创建者或全局管理员) + 内置公共智能体幂等种子。

use sea_orm::DatabaseConnection;

use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::pagination::{PaginationParams, PaginationResponse};

use crate::dao::agent as dao;
use crate::do_::agent::{AgentNew, AgentResp, AgentUpdate, AgentWorkflowSaveRequest};
use crate::do_::entity::agent;
use crate::seed::BUILTIN_AGENTS;
use crate::services::workflow;

/// 判断是否全局管理员(admin 角色穿透一切权限, 对齐 Python _is_admin)
pub async fn is_admin(user_id: &str) -> bool {
    let manager = module_authorization::casbin_mgr::auth();
    if !manager.ready().await {
        return false;
    }
    manager.has_grouping_policy(user_id, "admin", "*").await
}

/// 获取待管理智能体并校验归属(创建者或管理员)
///
/// :raises: 404 智能体不存在 / 400 非创建者且非管理员(文案对齐 Python)
async fn get_for_manage(
    db: &DatabaseConnection,
    agent_id: &str,
    user_id: &str,
) -> Result<agent::Model, AppError> {
    let Some(agent) = dao::get(db, agent_id).await? else {
        return Err(AppError::not_found(format!("未找到ID为 {agent_id} 的智能体")));
    };
    if agent.created_by.as_deref() != Some(user_id) && !is_admin(user_id).await {
        return Err(AppError::business("仅智能体创建者或管理员可操作"));
    }
    Ok(agent)
}

/// 分页获取用户可访问的智能体(公共 或 本人创建, 内置优先)
pub async fn list_accessible(
    db: &DatabaseConnection,
    user_id: &str,
    pagination: &PaginationParams,
) -> Result<PaginationResponse<AgentResp>, AppError> {
    let items = dao::list_accessible(db, user_id, pagination.offset(), pagination.limit()).await?;
    let total = dao::count_accessible(db, user_id).await?;
    Ok(PaginationResponse::create(items, total, pagination))
}

/// 按ID查询智能体
pub async fn get(db: &DatabaseConnection, agent_id: &str) -> Result<Option<AgentResp>, AppError> {
    dao::get(db, agent_id).await
}

/// 创建自定义智能体(私有, 仅创建者可用; 含类型与可选结构体配置)
pub async fn create(
    db: &DatabaseConnection,
    user_id: &str,
    data: &crate::do_::agent::AgentCreate,
) -> Result<String, AppError> {
    let new = AgentNew {
        id: dao::new_id(),
        name: data.name.trim().to_string(),
        description: data.description.trim().to_string(),
        system_prompt: data.system_prompt.trim().to_string(),
        agent_type: data.agent_type.unwrap_or_default(),
        workflow: None,
        input_type: data.input_type.unwrap_or_default(),
        output_type: data.output_type.unwrap_or_default(),
        input_schema: data.input_schema.clone(),
        output_schema: data.output_schema.clone(),
        is_public: false,
        is_builtin: false,
        created_by: Some(user_id.to_string()),
    };
    dao::add(db, new).await
}

/// 更新智能体(仅创建者或管理员; 归属/内置标记不可改)
pub async fn update(
    db: &DatabaseConnection,
    agent_id: &str,
    user_id: &str,
    patch: &AgentUpdate,
) -> Result<(), AppError> {
    let agent = get_for_manage(db, agent_id, user_id).await?;
    if patch.has_updates() {
        dao::update(db, &agent.id, patch).await?;
    }
    Ok(())
}

/// 删除智能体(仅创建者或管理员; 内置不可删除)
pub async fn delete(db: &DatabaseConnection, agent_id: &str, user_id: &str) -> Result<(), AppError> {
    let agent = get_for_manage(db, agent_id, user_id).await?;
    if agent.is_builtin {
        return Err(AppError::business("内置智能体不可删除"));
    }
    dao::delete(db, &agent.id).await
}

/// 保存工作流配置(切换智能体类型 + 保存图; 图先静态校验通过才落库)
///
/// - agent_type=workflow: workflow 图必填且须通过校验(节点/连线/引用/环检测)
/// - agent_type=simple: 不允许携带工作流图(切回简单类型即视为清除图)
pub async fn save_workflow(
    db: &DatabaseConnection,
    agent_id: &str,
    user_id: &str,
    data: &AgentWorkflowSaveRequest,
) -> Result<(), AppError> {
    let agent = get_for_manage(db, agent_id, user_id).await?;
    match data.agent_type {
        crate::do_::agent::AgentType::Workflow => {
            let errors = workflow::validate_workflow(data.workflow.as_ref());
            if !errors.is_empty() {
                return Err(AppError::business(format!(
                    "工作流校验失败: {}",
                    errors.join("; ")
                )));
            }
        }
        crate::do_::agent::AgentType::Simple => {
            if data.workflow.is_some() {
                return Err(AppError::business("简单智能体不支持工作流图, 请先切换为工作流类型"));
            }
        }
    }
    // 切回简单类型时显式清除图(对齐 Python AgentUpdate(workflow=None) 的清除语义)
    let patch = AgentUpdate {
        agent_type: Some(data.agent_type),
        workflow: data.workflow.clone(),
        clear_workflow: data.workflow.is_none(),
        ..Default::default()
    };
    dao::update(db, &agent.id, &patch).await
}

/// 内置公共智能体幂等写入(启动时调用; 已存在则跳过, 不覆盖用户可能的修改)
pub async fn seed_builtin_agents(state: &AppState) {
    let ids: Vec<String> = BUILTIN_AGENTS.iter().map(|a| a.id.to_string()).collect();
    let outcome: Result<(), AppError> = async {
        let existing = dao::list_by_ids(&state.db, &ids).await?;
        let existing_ids: Vec<&str> = existing.iter().map(|a| a.id.as_str()).collect();
        for item in BUILTIN_AGENTS.iter() {
            if existing_ids.contains(&item.id) {
                continue;
            }
            dao::add(&state.db, item.to_new_model()).await?;
            tracing::info!("内置智能体已写入: {}({})", item.name, item.id);
        }
        Ok(())
    }
    .await;
    // 种子失败不阻断启动(下次重启重试), 仅记录错误
    if let Err(e) = outcome {
        tracing::error!("内置智能体种子写入失败: {e}");
    }
}
