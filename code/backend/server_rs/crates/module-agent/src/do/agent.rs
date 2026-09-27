//! 智能体管理 DTO(对齐 Python module_agent/do/agent.py 的 Pydantic 模型部分)

use serde::{Deserialize, Serialize};
use serde_json::Value;

use common::utils::error::AppError;

/// 智能体输入/输出类型: str=纯字符串(默认), json=JSON 结构体
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum AgentIOType {
    #[default]
    Str,
    Json,
}

impl AgentIOType {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Str => "str",
            Self::Json => "json",
        }
    }

    /// 库中 VARCHAR 值解析(未知值回落 str, 与 Python 枚举存储口径一致)
    pub fn parse(value: &str) -> Self {
        if value == "json" {
            Self::Json
        } else {
            Self::Str
        }
    }
}

/// 智能体类型: simple=简单(单次 LLM 调用, 默认), workflow=工作流(Vue Flow 图编排)
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum AgentType {
    #[default]
    Simple,
    Workflow,
}

impl AgentType {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Simple => "simple",
            Self::Workflow => "workflow",
        }
    }

    /// 库中 VARCHAR 值解析(未知值回落 simple)
    pub fn parse(value: &str) -> Self {
        if value == "workflow" {
            Self::Workflow
        } else {
            Self::Simple
        }
    }
}

/// 智能体响应(直接序列化表实体, 字段与 Python SQLModel Agent 一致)
pub type AgentResp = crate::do_::entity::agent::Model;

/// 新增智能体的落库参数(dao 层转 ActiveModel)
#[derive(Debug, Clone)]
pub struct AgentNew {
    pub id: String,
    pub name: String,
    pub description: String,
    pub system_prompt: String,
    pub agent_type: AgentType,
    pub workflow: Option<Value>,
    pub input_type: AgentIOType,
    pub output_type: AgentIOType,
    pub input_schema: Option<Value>,
    pub output_schema: Option<Value>,
    pub is_public: bool,
    pub is_builtin: bool,
    pub created_by: Option<String>,
}

/// 创建智能体的请求模型(名称+描述+提示词, 可选类型与结构体配置)
#[derive(Debug, Clone, Deserialize)]
pub struct AgentCreate {
    pub name: String,
    #[serde(default)]
    pub description: String,
    pub system_prompt: String,
    #[serde(default)]
    pub agent_type: Option<AgentType>,
    #[serde(default)]
    pub input_type: Option<AgentIOType>,
    #[serde(default)]
    pub output_type: Option<AgentIOType>,
    #[serde(default)]
    pub input_schema: Option<Value>,
    #[serde(default)]
    pub output_schema: Option<Value>,
}

impl AgentCreate {
    /// 字段校验(对齐 Pydantic 约束: name≤100 / description≤500 / system_prompt≥1)
    pub fn validate(&self) -> Result<(), AppError> {
        check_len(Some(&self.name), 100, "name")?;
        check_len(Some(&self.description), 500, "description")?;
        check_len(Some(&self.system_prompt), usize::MAX, "system_prompt")?;
        Ok(())
    }
}

/// 字符串长度校验(超限构造 422, 文案对齐 Pydantic string_too_long)
fn check_len(value: Option<&str>, max: usize, field: &str) -> Result<(), AppError> {
    let Some(value) = value else {
        return Ok(());
    };
    if max != usize::MAX && value.chars().count() > max {
        return Err(AppError::validation(
            &["body", field],
            format!("String should have at most {max} characters"),
        ));
    }
    Ok(())
}

/// 更新智能体的请求模型(归属/内置标记不可改, 类型/结构体/工作流字段可选更新)
#[derive(Debug, Clone, Default, Deserialize)]
pub struct AgentUpdate {
    #[serde(default)]
    pub name: Option<String>,
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default)]
    pub system_prompt: Option<String>,
    #[serde(default)]
    pub agent_type: Option<AgentType>,
    #[serde(default)]
    pub workflow: Option<Value>,
    /// 显式清除工作流图(保存工作流接口切回 simple 类型时置位, 对齐 Python 显式传 workflow=None)
    #[serde(skip)]
    pub clear_workflow: bool,
    #[serde(default)]
    pub input_type: Option<AgentIOType>,
    #[serde(default)]
    pub output_type: Option<AgentIOType>,
    #[serde(default)]
    pub input_schema: Option<Value>,
    #[serde(default)]
    pub output_schema: Option<Value>,
}

impl AgentUpdate {
    /// 字段校验(仅校验显式传入的字段)
    pub fn validate(&self) -> Result<(), AppError> {
        check_len(self.name.as_deref(), 100, "name")?;
        check_len(self.description.as_deref(), 500, "description")?;
        if let Some(prompt) = self.system_prompt.as_deref() {
            if prompt.is_empty() {
                return Err(AppError::validation(
                    &["body", "system_prompt"],
                    "String should have at least 1 character",
                ));
            }
        }
        Ok(())
    }

    /// 补丁是否包含任一字段(空补丁不触发 DAO 更新)
    pub fn has_updates(&self) -> bool {
        self.name.is_some()
            || self.description.is_some()
            || self.system_prompt.is_some()
            || self.agent_type.is_some()
            || self.workflow.is_some()
            || self.input_type.is_some()
            || self.output_type.is_some()
            || self.input_schema.is_some()
            || self.output_schema.is_some()
    }
}

/// 保存工作流配置请求(切换智能体类型 + 保存工作流图, 保存前静态校验)
#[derive(Debug, Clone, Deserialize)]
pub struct AgentWorkflowSaveRequest {
    pub agent_type: AgentType,
    #[serde(default)]
    pub workflow: Option<Value>,
}
