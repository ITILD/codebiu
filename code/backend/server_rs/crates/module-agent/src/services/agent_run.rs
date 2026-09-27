//! 智能体运行服务(对齐 Python module_agent/service/agent_run.py)
//!
//! - simple 类型: agent.system_prompt 作为任务提示词(系统角色), 输入数据与结构要求作为用户消息
//! - workflow 类型: 交给 WorkflowService 按图执行, 节点轨迹随运行历史落库
//! - output_type=json 时以提示词约束 JSON 输出并容错解析
//! - 运行记录写入 agent_run 历史表(仅本人可见; 工作流失败也落库便于排查)

use sea_orm::DatabaseConnection;
use serde_json::{json, Value};

use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::pagination::{PaginationParams, PaginationResponse};

use crate::dao::agent as agent_dao;
use crate::dao::agent_run as run_dao;
use crate::do_::agent::AgentIOType;
use crate::do_::agent_run::{AgentRunHistory, AgentRunRequest, AgentRunResponse};
use crate::do_::entity::agent;
use crate::services::workflow::{self, NodeTrace};

/// 运行系统角色提示词(沿用原数据清洗的语义, 叠加 agent 自身提示词)
const RUN_SYSTEM_PROMPT: &str = "你是一名数据处理助手, 负责根据智能体配置的任务提示词, \
对输入的数据(JSON 或文本)进行处理并按要求的结构输出。\n\
要求:\n\
1. 严格遵循任务提示词执行, 不要添加与任务无关的内容;\n\
2. 保持数据语义不变, 仅按任务要求做格式、噪声、冗余与一致性处理;\n\
3. 输出只包含处理结果, 不要输出解释或 Markdown 代码块标记。";

/// 校验智能体可运行(存在且公共或本人创建)
///
/// :raises: 404 智能体不存在 / 403 非公共且非本人创建(文案对齐 Python)
async fn get_runnable(
    db: &DatabaseConnection,
    agent_id: &str,
    user_id: &str,
) -> Result<agent::Model, AppError> {
    let Some(agent) = agent_dao::get(db, agent_id).await? else {
        return Err(AppError::not_found(format!("未找到ID为 {agent_id} 的智能体")));
    };
    if !agent.is_public && agent.created_by.as_deref() != Some(user_id) {
        return Err(AppError::forbidden("仅公共智能体或本人创建的智能体可运行"));
    }
    Ok(agent)
}

/// 执行一次运行: 校验可访问性 → 按类型分流(工作流/简单) → 持久化运行历史
pub async fn run(
    state: &AppState,
    agent_id: &str,
    user_id: &str,
    request: &AgentRunRequest,
) -> Result<AgentRunResponse, AppError> {
    let agent = get_runnable(&state.db, agent_id, user_id).await?;

    // 工作流智能体: 图执行 + 轨迹(不走简单的单次 LLM 链路)
    if crate::do_::agent::AgentType::parse(&agent.agent_type) == crate::do_::agent::AgentType::Workflow {
        return run_workflow_agent(state, &agent, user_id, request).await;
    }

    let Some(target) = module_ai::services::llm::get_llm(&state.db, &request.model_id, false).await?
    else {
        return Err(AppError::not_found("模型配置不存在或不可用"));
    };

    let messages = build_messages(&agent, &request.input.0);
    let result = run_llm(&state.http, &target, &messages, &agent).await?;

    let run_id = run_dao::add(
        &state.db,
        run_dao::RunNew {
            id: agent_dao::new_id(),
            agent_id: agent.id.clone(),
            user_id: user_id.to_string(),
            model_id: request.model_id.clone(),
            input: request.input.0.clone(),
            output: result.clone(),
            trace: None,
        },
    )
    .await?;
    Ok(AgentRunResponse {
        run_id,
        result,
        trace: None,
    })
}

/// 工作流智能体执行: 图驱动 + 轨迹落库(失败也落库, 便于排查后重试)
async fn run_workflow_agent(
    state: &AppState,
    agent: &agent::Model,
    user_id: &str,
    request: &AgentRunRequest,
) -> Result<AgentRunResponse, AppError> {
    let service = workflow::WorkflowService;
    let (result, traces) = match service.run_workflow(state, agent, request).await {
        Ok(pair) => pair,
        Err(e) => {
            tracing::warn!("工作流执行失败(agent={}): {}", agent.id, e.message);
            // 失败轨迹也落库, 便于排查后重试
            run_dao::add(
                &state.db,
                run_dao::RunNew {
                    id: agent_dao::new_id(),
                    agent_id: agent.id.clone(),
                    user_id: user_id.to_string(),
                    model_id: request.model_id.clone(),
                    input: request.input.0.clone(),
                    output: json!({ "error": e.message }),
                    trace: Some(trace_payload(&e.traces)),
                },
            )
            .await?;
            return Err(AppError::business(format!("工作流执行失败: {}", e.message)));
        }
    };
    let run_id = run_dao::add(
        &state.db,
        run_dao::RunNew {
            id: agent_dao::new_id(),
            agent_id: agent.id.clone(),
            user_id: user_id.to_string(),
            model_id: request.model_id.clone(),
            input: request.input.0.clone(),
            output: result.clone(),
            trace: Some(trace_payload(&traces)),
        },
    )
    .await?;
    Ok(AgentRunResponse {
        run_id,
        result,
        trace: Some(traces.iter().map(|t| serde_json::to_value(t).unwrap_or(Value::Null)).collect()),
    })
}

/// 轨迹序列化为 JSON 存储结构({'nodes': [...]}, 对齐 Python _trace_payload)
fn trace_payload(traces: &[NodeTrace]) -> Value {
    json!({ "nodes": traces })
}

/// 分页获取本人运行历史(按运行时间倒序; 智能体不存在时 404)
pub async fn list_runs(
    db: &DatabaseConnection,
    agent_id: &str,
    user_id: &str,
    pagination: &PaginationParams,
) -> Result<PaginationResponse<AgentRunHistory>, AppError> {
    if agent_dao::get(db, agent_id).await?.is_none() {
        return Err(AppError::not_found(format!("未找到ID为 {agent_id} 的智能体")));
    }
    let items = run_dao::list_by_agent_user(db, agent_id, user_id, pagination.offset(), pagination.limit())
        .await?;
    let total = run_dao::count_by_agent_user(db, agent_id, user_id).await?;
    Ok(PaginationResponse::create(
        items.iter().map(history_from).collect(),
        total,
        pagination,
    ))
}

/// 查询单条运行详情(含工作流节点轨迹; 仅本人记录, 智能体/记录不存在时 404)
pub async fn get_run_detail(
    db: &DatabaseConnection,
    agent_id: &str,
    run_id: &str,
    user_id: &str,
) -> Result<AgentRunHistory, AppError> {
    if agent_dao::get(db, agent_id).await?.is_none() {
        return Err(AppError::not_found(format!("未找到ID为 {agent_id} 的智能体")));
    }
    let run = run_dao::get_run(db, run_id, user_id).await?;
    match run {
        Some(run) if run.agent_id == agent_id => Ok(history_from(&run)),
        _ => Err(AppError::not_found(format!("未找到运行记录 {run_id}"))),
    }
}

/// 运行记录实体 → 响应视图
fn history_from(run: &crate::do_::entity::agent_run::Model) -> AgentRunHistory {
    AgentRunHistory {
        id: run.id.clone(),
        agent_id: run.agent_id.clone(),
        model_id: run.model_id.clone(),
        input: run.input.clone(),
        output: run.output.clone(),
        trace: run.trace.clone(),
        created_at: run.created_at,
    }
}

/// 单次 LLM 推理: output_type=str 直出文本, json 按提示词约束解析(对齐 _run_string/_run_json)
async fn run_llm(
    http: &reqwest::Client,
    target: &module_ai::utils::llm::LlmTarget,
    messages: &[module_ai::do_::llm::Message],
    agent: &agent::Model,
) -> Result<Value, AppError> {
    let content = module_ai::utils::llm::chat_once(http, target, messages).await?;
    if AgentIOType::parse(&agent.output_type) == AgentIOType::Json {
        Ok(workflow::parse_json_content(&workflow::content_text(&content)))
    } else {
        // 字符串输出: 直接返回模型文本结果(非字符串形态 JSON 序列化, 对齐 _run_string)
        Ok(match content {
            Value::String(s) => Value::String(s),
            other => Value::String(other.to_string()),
        })
    }
}

/// 构造 LLM 消息: 系统角色(运行约束+agent 提示词) + 用户内容(输入/结构要求)
fn build_messages(agent: &agent::Model, input: &Value) -> Vec<module_ai::do_::llm::Message> {
    let data_text = match input {
        Value::String(s) => s.clone(),
        other => serde_json::to_string_pretty(other).unwrap_or_default(),
    };
    let mut user_content = vec![
        format!("### 任务提示词\n{}", agent.system_prompt),
        format!("### 输入数据\n{data_text}"),
    ];
    let input_type = AgentIOType::parse(&agent.input_type);
    let output_type = AgentIOType::parse(&agent.output_type);
    if input_type == AgentIOType::Json {
        if let Some(schema) = &agent.input_schema {
            user_content.push(format!(
                "### 输入结构说明(输入数据应符合此 JSON Schema)\n{}",
                serde_json::to_string_pretty(schema).unwrap_or_default()
            ));
        }
    }
    if output_type == AgentIOType::Json {
        match &agent.output_schema {
            Some(schema) => user_content.push(format!(
                "### 输出结构要求(必须严格遵循此 JSON Schema)\n{}",
                serde_json::to_string_pretty(schema).unwrap_or_default()
            )),
            None => user_content.push(
                "### 输出结构要求\n输出合法的 JSON(对象或数组), 不要包含 Markdown 代码块标记。".to_string(),
            ),
        }
    }
    vec![
        message("system", RUN_SYSTEM_PROMPT),
        message("user", &user_content.join("\n\n")),
    ]
}

/// 单条消息构造
fn message(role: &str, content: &str) -> module_ai::do_::llm::Message {
    module_ai::do_::llm::Message {
        role: role.to_string(),
        content: content.to_string(),
        additional_kwargs: Value::Null,
    }
}
