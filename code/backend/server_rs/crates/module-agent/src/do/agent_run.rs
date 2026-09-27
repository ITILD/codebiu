//! 智能体运行 DTO(对齐 Python module_agent/do/agent_run.py 的 Pydantic 模型部分)

use chrono::{DateTime, FixedOffset};
use serde::{Deserialize, Serialize};
use serde_json::Value;

/// 运行输入载体: 字符串入参先尝试解析为 JSON, 解析失败按原字符串处理(对齐 parse_input 校验器)
#[derive(Debug, Clone)]
pub struct RunInput(pub Value);

impl<'de> Deserialize<'de> for RunInput {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        let value = Value::deserialize(deserializer)?;
        if let Value::String(text) = &value {
            if let Ok(parsed) = serde_json::from_str::<Value>(text.trim()) {
                return Ok(Self(parsed));
            }
        }
        Ok(Self(value))
    }
}

/// 运行智能体请求(model_id: 模型配置ID或模型标识名称; input 类型须匹配 agent.input_type)
#[derive(Debug, Clone, Deserialize)]
pub struct AgentRunRequest {
    pub model_id: String,
    pub input: RunInput,
}

/// 运行智能体响应
#[derive(Debug, Clone, Serialize)]
pub struct AgentRunResponse {
    /// 本次运行记录ID(运行历史可回看)
    pub run_id: String,
    /// 运行结果: output_type=str 时为字符串, json 时为结构化对象
    pub result: Value,
    /// 工作流节点执行轨迹(仅工作流智能体返回, 每节点输入/输出/耗时/状态)
    pub trace: Option<Vec<Value>>,
}

/// 运行历史条目(响应视图)
#[derive(Debug, Clone, Serialize)]
pub struct AgentRunHistory {
    pub id: String,
    pub agent_id: String,
    pub model_id: String,
    pub input: Value,
    pub output: Value,
    /// 工作流节点执行轨迹({'nodes': [...]}, 仅工作流智能体)
    pub trace: Option<Value>,
    pub created_at: Option<DateTime<FixedOffset>>,
}
