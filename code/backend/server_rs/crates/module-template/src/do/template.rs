//! 模板数据对象(对齐 Python module_template/do/template.py)

use serde::Deserialize;

use common::utils::error::{validation, AppError, ValidationErrorItem};

/// 创建模板请求(TemplateCreate; 未传字段取 Python 模型默认值)
#[derive(Debug, Deserialize)]
pub struct TemplateCreate {
    /// 父级ID
    #[serde(default)]
    pub pid: Option<String>,
    /// 数值字段(默认 0)
    #[serde(default)]
    pub value: Option<i32>,
    /// 模板名称
    #[serde(default)]
    pub name: Option<String>,
    /// 模板描述(最长 500)
    #[serde(default)]
    pub description: Option<String>,
    /// 是否激活状态(默认 true)
    #[serde(default)]
    pub is_active: Option<bool>,
}

/// 更新模板请求(TemplateUpdate, 全部可选仅更新传入字段)
#[derive(Debug, Default, Deserialize)]
pub struct TemplateUpdate {
    /// 父级ID(可空: 传 null 置 NULL)
    #[serde(default)]
    pub pid: Option<Option<String>>,
    /// 数值字段
    #[serde(default)]
    pub value: Option<i32>,
    /// 模板名称(可空: 传 null 置 NULL)
    #[serde(default)]
    pub name: Option<Option<String>>,
    /// 模板描述(可空: 传 null 置 NULL)
    #[serde(default)]
    pub description: Option<Option<String>>,
    /// 是否激活(可空: 传 null 置 NULL)
    #[serde(default)]
    pub is_active: Option<Option<bool>>,
}

/// 批量删除模板请求(TemplateBatchDelete)
#[derive(Debug, Deserialize)]
pub struct TemplateBatchDelete {
    /// 要删除的模板ID列表(1~200, 不允许空白ID)
    pub ids: Vec<String>,
}

impl TemplateBatchDelete {
    /// 校验 ID 列表(对齐 pydantic 长度约束与 field_validator, 违规构造 422)
    pub fn validate(&self) -> Result<(), AppError> {
        if self.ids.is_empty() {
            return Err(list_length_error(
                "too_short",
                "List should have at least 1 item after validation, not 0",
            ));
        }
        if self.ids.len() > 200 {
            return Err(list_length_error(
                "too_long",
                format!(
                    "List should have at most 200 items after validation, not {}",
                    self.ids.len()
                ),
            ));
        }
        if self.ids.iter().any(|id| id.trim().is_empty()) {
            // Python pydantic 会给 field_validator 的 ValueError 加 "Value error, " 前缀
            return Err(validation(&["body", "ids"], "Value error, ID 不能为空或仅包含空白字符"));
        }
        Ok(())
    }
}

/// 构造列表长度类 422 校验错误(type=too_short/too_long 与 FastAPI 一致)
fn list_length_error(error_type: &str, msg: impl Into<String>) -> AppError {
    AppError::Validation(vec![ValidationErrorItem {
        loc: vec!["body".to_string(), "ids".to_string()],
        msg: msg.into(),
        error_type: error_type.to_string(),
    }])
}
