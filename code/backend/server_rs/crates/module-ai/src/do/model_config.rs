//! 模型配置 DTO(对齐 Python module_ai/do/model_config.py)

use chrono::{SecondsFormat, Utc};
use sea_orm::prelude::DateTimeWithTimeZone;
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::do_::entity::model_config;

/// 归属范围: public=所有人可见可用 / dept=所属部门 / user=仅本人
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ModelScope {
    Public,
    Dept,
    User,
}

impl ModelScope {
    /// 数据库存取字符串(与 Python StrEnum value 一致)
    pub fn as_str(self) -> &'static str {
        match self {
            ModelScope::Public => "public",
            ModelScope::Dept => "dept",
            ModelScope::User => "user",
        }
    }
}

fn d_chat() -> String {
    "chat".to_string()
}
fn d_openai() -> String {
    "openai".to_string()
}
fn d_user_scope() -> ModelScope {
    ModelScope::User
}
fn d_true() -> bool {
    true
}
fn d_zero() -> f64 {
    0.0
}
fn d_8192() -> i32 {
    8192
}
fn d_temp() -> f64 {
    0.7
}
fn d_60() -> i32 {
    60
}

/// 创建模型配置请求体(字段与默认值对齐 Python ModelConfigBase)
#[derive(Debug, Clone, Deserialize)]
pub struct ModelConfigCreateRequest {
    #[serde(default = "d_chat")]
    pub model_type: String,
    #[serde(default = "d_openai")]
    pub server_type: String,
    pub model: String,
    #[serde(default)]
    pub url: Option<String>,
    #[serde(default)]
    pub api_key: Option<String>,
    #[serde(default = "d_user_scope")]
    pub scope: ModelScope,
    #[serde(default)]
    pub dept_id: Option<String>,
    #[serde(default)]
    pub is_default: bool,
    #[serde(default = "d_true")]
    pub is_active: bool,
    #[serde(default)]
    pub display_name: Option<String>,
    #[serde(default = "d_zero")]
    pub pay_in: f64,
    #[serde(default = "d_zero")]
    pub pay_out: f64,
    #[serde(default = "d_8192")]
    pub input_tokens: i32,
    #[serde(default = "d_8192")]
    pub out_tokens: i32,
    #[serde(default = "d_temp")]
    pub temperature: f64,
    #[serde(default = "d_60")]
    pub timeout: i32,
    #[serde(default)]
    pub no_think: Option<bool>,
    #[serde(default)]
    pub extra: Option<Value>,
}

impl ModelConfigCreateRequest {
    /// 按 server_type 补默认 url(对齐 Python model_validator set_default_url, 仅 url 未提供时)
    pub fn apply_default_url(&mut self) {
        if self.url.is_some() {
            return;
        }
        self.url = Some(match self.server_type.as_str() {
            "dashscope" => "https://dashscope.aliyuncs.com/compatible-mode/v1".to_string(),
            "vllm" => "http://localhost:8000/v1".to_string(),
            "aws" => "https://bedrock-runtime.us-east-1.amazonaws.com".to_string(),
            "ollama" => "http://localhost:11434".to_string(),
            // openai 及其他未知方案回落官方地址
            _ => "https://api.openai.com/v1".to_string(),
        });
    }

    /// 请求字段范围校验(对齐 pydantic 字段约束, 违反构造 422)
    pub fn validate(&self) -> Result<(), common::utils::error::AppError> {
        use common::utils::error::AppError;
        if self.pay_in < 0.0 || self.pay_out < 0.0 {
            return Err(AppError::validation(&["body", "pay_in"], "Input should be greater than or equal to 0"));
        }
        if self.out_tokens <= 0 {
            return Err(AppError::validation(&["body", "out_tokens"], "Input should be greater than 0"));
        }
        if !(0.0..=2.0).contains(&self.temperature) {
            return Err(AppError::validation(&["body", "temperature"], "Input should be between 0 and 2"));
        }
        if self.timeout <= 0 {
            return Err(AppError::validation(&["body", "timeout"], "Input should be greater than 0"));
        }
        Ok(())
    }

    /// 转为服务层创建对象(补充归属用户)
    pub fn into_create(self, user_id: String) -> ModelConfigCreate {
        ModelConfigCreate {
            model_type: self.model_type,
            server_type: self.server_type,
            model: self.model,
            url: self.url,
            api_key: self.api_key,
            scope: self.scope,
            dept_id: self.dept_id,
            is_default: self.is_default,
            is_active: self.is_active,
            display_name: self.display_name,
            pay_in: self.pay_in,
            pay_out: self.pay_out,
            input_tokens: self.input_tokens,
            out_tokens: self.out_tokens,
            temperature: self.temperature,
            timeout: self.timeout,
            no_think: self.no_think,
            extra: self.extra,
            user_id,
        }
    }
}

/// 服务层创建对象(带归属用户)
#[derive(Debug, Clone)]
pub struct ModelConfigCreate {
    pub model_type: String,
    pub server_type: String,
    pub model: String,
    pub url: Option<String>,
    pub api_key: Option<String>,
    pub scope: ModelScope,
    pub dept_id: Option<String>,
    pub is_default: bool,
    pub is_active: bool,
    pub display_name: Option<String>,
    pub pay_in: f64,
    pub pay_out: f64,
    pub input_tokens: i32,
    pub out_tokens: i32,
    pub temperature: f64,
    pub timeout: i32,
    pub no_think: Option<bool>,
    pub extra: Option<Value>,
    pub user_id: String,
}

/// 部分更新对象(仅显式传入字段生效, 对齐 Python ModelConfigUpdate)
#[derive(Debug, Clone, Default, Deserialize)]
pub struct ModelConfigUpdate {
    #[serde(default)]
    pub model_type: Option<String>,
    #[serde(default)]
    pub server_type: Option<String>,
    #[serde(default)]
    pub model: Option<String>,
    #[serde(default)]
    pub url: Option<String>,
    #[serde(default)]
    pub api_key: Option<String>,
    #[serde(default)]
    pub scope: Option<ModelScope>,
    #[serde(default)]
    pub dept_id: Option<String>,
    #[serde(default)]
    pub is_default: Option<bool>,
    #[serde(default)]
    pub is_active: Option<bool>,
    #[serde(default)]
    pub display_name: Option<String>,
    #[serde(default)]
    pub pay_in: Option<f64>,
    #[serde(default)]
    pub pay_out: Option<f64>,
    #[serde(default)]
    pub input_tokens: Option<i32>,
    #[serde(default)]
    pub out_tokens: Option<i32>,
    #[serde(default)]
    pub temperature: Option<f64>,
    #[serde(default)]
    pub timeout: Option<i32>,
    #[serde(default)]
    pub no_think: Option<bool>,
    #[serde(default)]
    pub extra: Option<Value>,
    // 最近校验结果(仅由后台自动校验/能力测试回写)
    #[serde(default)]
    pub check_valid: Option<bool>,
    #[serde(default)]
    pub check_format: Option<bool>,
    #[serde(default)]
    pub checked_at: Option<DateTimeWithTimeZone>,
    #[serde(default)]
    pub check_result: Option<Value>,
    /// 服务层内部标记: 切换归属范围离开 dept 时清除部门列(不参与反序列化)
    #[serde(skip)]
    pub clear_dept_id: bool,
}

fn now_tz() -> DateTimeWithTimeZone {
    Utc::now().with_timezone(&chrono::FixedOffset::east_opt(0).expect("UTC 偏移合法"))
}

impl ModelConfigCreate {
    /// 转为 SeaORM 插入模型(id 由调用方/本方法生成, 主键为 32 位 hex uuid)
    pub fn to_active_model(&self, id: String) -> model_config::ActiveModel {
        model_config::ActiveModel {
            id: sea_orm::Set(id),
            model_type: sea_orm::Set(self.model_type.clone()),
            server_type: sea_orm::Set(self.server_type.clone()),
            model: sea_orm::Set(self.model.clone()),
            url: sea_orm::Set(self.url.clone()),
            api_key: sea_orm::Set(self.api_key.clone()),
            scope: sea_orm::Set(self.scope.as_str().to_string()),
            dept_id: sea_orm::Set(self.dept_id.clone()),
            is_default: sea_orm::Set(self.is_default),
            is_active: sea_orm::Set(self.is_active),
            display_name: sea_orm::Set(self.display_name.clone()),
            pay_in: sea_orm::Set(Some(self.pay_in)),
            pay_out: sea_orm::Set(Some(self.pay_out)),
            input_tokens: sea_orm::Set(Some(self.input_tokens)),
            out_tokens: sea_orm::Set(Some(self.out_tokens)),
            temperature: sea_orm::Set(Some(self.temperature)),
            timeout: sea_orm::Set(Some(self.timeout)),
            no_think: sea_orm::Set(Some(self.no_think.unwrap_or(false))),
            extra: sea_orm::Set(self.extra.clone()),
            user_id: sea_orm::Set(self.user_id.clone()),
            // 遗留共享标记列: 与 scope 保持一致(Python 侧已由 scope 取代)
            is_public: sea_orm::Set(self.scope == ModelScope::Public),
            check_valid: sea_orm::Set(None),
            check_format: sea_orm::Set(None),
            checked_at: sea_orm::Set(None),
            check_result: sea_orm::Set(None),
            created_at: sea_orm::Set(Some(now_tz())),
            updated_at: sea_orm::Set(now_tz()),
        }
    }
}

/// 模型配置响应体(字段与 Python ModelConfig 读模型一致, 不含遗留 is_public)
#[derive(Debug, Clone, Serialize)]
pub struct ModelConfigResp {
    pub id: String,
    pub user_id: String,
    pub model_type: String,
    pub server_type: String,
    pub model: String,
    pub url: Option<String>,
    pub api_key: Option<String>,
    pub scope: String,
    pub dept_id: Option<String>,
    pub is_default: bool,
    pub is_active: bool,
    pub display_name: Option<String>,
    pub pay_in: Option<f64>,
    pub pay_out: Option<f64>,
    pub input_tokens: Option<i32>,
    pub out_tokens: Option<i32>,
    pub temperature: Option<f64>,
    pub timeout: Option<i32>,
    pub no_think: Option<bool>,
    pub extra: Option<Value>,
    pub check_valid: Option<bool>,
    pub check_format: Option<bool>,
    pub checked_at: Option<DateTimeWithTimeZone>,
    pub check_result: Option<Value>,
    pub created_at: Option<DateTimeWithTimeZone>,
    pub updated_at: DateTimeWithTimeZone,
}

impl From<model_config::Model> for ModelConfigResp {
    fn from(m: model_config::Model) -> Self {
        Self {
            id: m.id,
            user_id: m.user_id,
            model_type: m.model_type,
            server_type: m.server_type,
            model: m.model,
            url: m.url,
            api_key: m.api_key,
            scope: m.scope,
            dept_id: m.dept_id,
            is_default: m.is_default,
            is_active: m.is_active,
            display_name: m.display_name,
            pay_in: m.pay_in,
            pay_out: m.pay_out,
            input_tokens: m.input_tokens,
            out_tokens: m.out_tokens,
            temperature: m.temperature,
            timeout: m.timeout,
            no_think: m.no_think,
            extra: m.extra,
            check_valid: m.check_valid,
            check_format: m.check_format,
            checked_at: m.checked_at,
            check_result: m.check_result,
            created_at: m.created_at,
            updated_at: m.updated_at,
        }
    }
}

/// 当前时间(UTC, RFC3339 字符串; 校验明细 checked_at 用)
pub fn now_iso() -> String {
    Utc::now().to_rfc3339_opts(SecondsFormat::Secs, true)
}
