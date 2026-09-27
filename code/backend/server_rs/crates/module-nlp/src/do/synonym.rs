//! 同义词数据对象(对齐 Python module_nlp/do/synonym.py)

use serde::{Deserialize, Serialize};

/// 创建同义词组请求(SynonymGroupCreate)
#[derive(Debug, Deserialize)]
pub struct SynonymGroupCreate {
    /// 项目ID
    pub pid: String,
    /// 同义词组名称
    pub name: String,
    /// 同义词组描述
    #[serde(default)]
    pub description: Option<String>,
    /// 是否激活状态(默认 true)
    #[serde(default)]
    pub is_active: Option<bool>,
}

/// 更新同义词组请求(SynonymGroupUpdate, 全部可选仅更新传入字段)
#[derive(Debug, Default, Deserialize)]
pub struct SynonymGroupUpdate {
    /// 项目ID
    #[serde(default)]
    pub pid: Option<String>,
    /// 同义词组名称
    #[serde(default)]
    pub name: Option<String>,
    /// 同义词组描述(可空: 传 null 置 NULL)
    #[serde(default)]
    pub description: Option<Option<String>>,
    /// 是否激活(可空: 传 null 置 NULL)
    #[serde(default)]
    pub is_active: Option<Option<bool>>,
}

/// 批量删除请求(同义词组/同义词共用, 对齐 SynonymGroupBatchDelete 与 SynonymBatchDelete)
#[derive(Debug, Deserialize)]
pub struct BatchIdsRequest {
    /// 要删除的ID列表(1~200)
    pub ids: Vec<String>,
}

impl BatchIdsRequest {
    /// 校验 ID 列表(对齐 pydantic 长度约束, 违规构造 422)
    pub fn validate(&self) -> Result<(), common::utils::error::AppError> {
        use common::utils::error::{validation, AppError, ValidationErrorItem};
        let length_error = |error_type: &str, msg: String| {
            AppError::Validation(vec![ValidationErrorItem {
                loc: vec!["body".to_string(), "ids".to_string()],
                msg,
                error_type: error_type.to_string(),
            }])
        };
        if self.ids.is_empty() {
            return Err(length_error(
                "too_short",
                "List should have at least 1 item after validation, not 0".to_string(),
            ));
        }
        if self.ids.len() > 200 {
            return Err(length_error(
                "too_long",
                format!(
                    "List should have at most 200 items after validation, not {}",
                    self.ids.len()
                ),
            ));
        }
        if self.ids.iter().any(|id| id.trim().is_empty()) {
            return Err(validation(&["body", "ids"], "Value error, ID 不能为空或仅包含空白字符"));
        }
        Ok(())
    }
}

/// 批量创建同义词请求(SynonymBatchCreate)
#[derive(Debug, Deserialize)]
pub struct SynonymBatchCreate {
    /// 项目ID
    pub pid: String,
    /// 所属同义词组ID
    pub group_id: String,
    /// 同义词列表(1~200)
    pub words: Vec<String>,
    /// 语言代码
    #[serde(default)]
    pub language: Option<String>,
}

/// 批量搜索同义词请求(SynonymBatchSearch)
#[derive(Debug, Deserialize)]
pub struct SynonymBatchSearch {
    /// 要搜索的词语列表(1~200)
    pub words: Vec<String>,
    /// 语言代码(可选)
    #[serde(default)]
    pub language: Option<String>,
}

/// 批量更新同义词请求(SynonymBatchUpdate)
#[derive(Debug, Deserialize)]
pub struct SynonymBatchUpdate {
    /// 项目ID
    pub pid: String,
    /// 目标同义词列表(1~200)
    pub words: Vec<String>,
    /// 语言代码
    #[serde(default)]
    pub language: Option<String>,
}

/// 同义词分组结果(SynonymBatchSearchResult)
#[derive(Debug, Serialize)]
pub struct SynonymBatchSearchResult {
    /// 搜索的词(输入词里的同义词也返回)
    pub words: Vec<String>,
    /// 扩展同义词(排除输入词后的组内词语)
    pub synonyms: Vec<String>,
}
