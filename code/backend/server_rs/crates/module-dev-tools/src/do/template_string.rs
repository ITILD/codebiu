//! 模板字符串数据对象(对齐 Python module_dev_tools/do/template_string.py)

use serde::{Deserialize, Serialize};

/// 创建模板字符串请求(TemplateStringCreate)
#[derive(Debug, Deserialize)]
pub struct TemplateStringCreate {
    /// 模板名称
    pub name: String,
    /// 模板描述
    #[serde(default)]
    pub description: Option<String>,
    /// 模板内容(支持 ${variable} 格式)
    pub template_content: String,
    /// 模板分类
    #[serde(default)]
    pub category: Option<String>,
    /// 标签(未传/显式 null/空列表时自动从模板内容提取, 对齐 Python default_factory + 提取逻辑)
    #[serde(default)]
    pub tags: Option<Option<Vec<String>>>,
    /// 是否激活状态(默认 true)
    #[serde(default)]
    pub is_active: Option<bool>,
}

/// 更新模板字符串请求(TemplateStringUpdate, 全部可选仅更新传入字段)
#[derive(Debug, Default, Deserialize)]
pub struct TemplateStringUpdate {
    /// 模板名称
    #[serde(default)]
    pub name: Option<String>,
    /// 模板描述(可空: 传 null 置 NULL)
    #[serde(default)]
    pub description: Option<Option<String>>,
    /// 模板内容
    #[serde(default)]
    pub template_content: Option<String>,
    /// 模板分类(可空: 传 null 置 NULL)
    #[serde(default)]
    pub category: Option<Option<String>>,
    /// 标签(可空: 传 null 置 NULL; 更新不做自动提取, 对齐 Python)
    #[serde(default)]
    pub tags: Option<Option<Vec<String>>>,
    /// 是否激活状态
    #[serde(default)]
    pub is_active: Option<bool>,
}

/// 模板渲染请求(TemplateRenderRequest)
#[derive(Debug, Deserialize)]
pub struct TemplateRenderRequest {
    /// 模板ID(提供时优先按ID从库中读取模板)
    #[serde(default)]
    pub template_id: Option<String>,
    /// 直接提供的模板内容
    #[serde(default)]
    pub template_content: Option<String>,
    /// 模板变量字典(缺省空)
    #[serde(default)]
    pub variables: std::collections::HashMap<String, String>,
}

/// 模板渲染响应(TemplateRenderResponse)
#[derive(Debug, Serialize)]
pub struct TemplateRenderResponse {
    /// 渲染后的内容
    pub rendered_content: String,
    /// 使用的模板ID
    pub template_id: Option<String>,
    /// 使用的变量列表
    pub variables_used: Vec<String>,
    /// 缺失的变量列表
    pub variables_missing: Vec<String>,
}

/// 模板语法校验响应(对齐 Python validate_template_syntax 返回的 dict)
#[derive(Debug, Serialize)]
pub struct TemplateValidateResponse {
    /// 语法是否有效
    pub valid: bool,
    /// 提取到的变量列表
    pub variables: Vec<String>,
    /// 校验结果消息
    pub message: String,
}
