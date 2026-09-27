//! 起名推测/生成请求与旧端点兼容响应(对齐 Python module_life/do/baby_name.py 的非表请求模型)

use serde::{Deserialize, Serialize};

/// 宝宝天生信息(NameInfoBase)
#[derive(Debug, Deserialize)]
pub struct NameInfoBase {
    /// 出生日期(公历 YYYY-MM-DD)
    pub birth_date: String,
    /// 出生时间(24 小时制 HH:mm)
    pub birth_time: String,
    pub gender: crate::do_::baby_name::Gender,
    /// 姓氏
    pub surname: String,
}

/// 思考模式(think_mode: off=关闭, low/medium/high=思考深度档位)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ThinkMode {
    Off,
    Low,
    Medium,
    High,
}

/// AI 起名流式请求(BabyNameGenerateRequest)
#[derive(Debug, Deserialize)]
pub struct BabyNameGenerateRequest {
    pub birth_date: String,
    pub birth_time: String,
    pub gender: crate::do_::baby_name::Gender,
    pub surname: String,
    /// 名字字数(不含姓, 默认 2)
    #[serde(default = "default_name_length")]
    pub name_length: i32,
    /// 补充信息(默认空)
    #[serde(default)]
    pub other: Option<String>,
    /// 模型ID(留空自动使用默认公共 chat 模型)
    #[serde(default)]
    pub model_id: Option<String>,
    /// 参考的民俗/神话体系(多选, 默认空)
    #[serde(default)]
    pub references: Vec<crate::utils::baby_name::folklore::Reference>,
    /// 本次生成名字数量(1-50, 默认 20)
    #[serde(default = "default_count")]
    pub count: i32,
    /// 需避开的历史名字(生成更多时防重复, 默认空)
    #[serde(default)]
    pub exclude_names: Vec<String>,
    /// 思考模式(默认 off)
    #[serde(default)]
    pub think_mode: Option<ThinkMode>,
}

fn default_name_length() -> i32 {
    2
}

fn default_count() -> i32 {
    20
}

/// 旧版完整推测请求(NameInfoPredictFullRequest, model_id 必填)
#[derive(Debug, Deserialize)]
pub struct NameInfoPredictFullRequest {
    pub birth_date: String,
    pub birth_time: String,
    pub gender: crate::do_::baby_name::Gender,
    pub surname: String,
    #[serde(default = "default_name_length")]
    pub name_length: i32,
    #[serde(default)]
    pub other: Option<String>,
    /// 模型ID(必填)
    pub model_id: String,
}

/// 参考体系推算请求(ReferenceCalculateRequest = NameInfoBase + references)
#[derive(Debug, Deserialize)]
pub struct ReferenceCalculateRequest {
    pub birth_date: String,
    pub birth_time: String,
    pub gender: crate::do_::baby_name::Gender,
    pub surname: String,
    /// 要推算的参考体系列表(strict 项才参与计算)
    pub references: Vec<crate::utils::baby_name::folklore::Reference>,
}

// ############################# 旧端点兼容响应(桩) #############################

/// 推测的五行星座偏好(NameInfoPreference)
#[derive(Debug, Serialize)]
pub struct NameInfoPreference {
    /// 五行偏好(起名宜补, 按优先级)
    pub wuxing_preference: Vec<String>,
    /// 星座偏好
    pub constellation_preference: Vec<String>,
}

/// 推测结果与解释(NameInfoResult)
#[derive(Debug, Serialize)]
pub struct NameInfoResult {
    pub name: String,
    pub explanation_wuxing: String,
    pub explanation_constellation: String,
    pub explanation_meaning: String,
}

/// 姓名基础信息请求(NameInfoResultBase, 仅含完整名字)
#[derive(Debug, Deserialize)]
pub struct NameInfoResultBase {
    /// 宝宝完整名字
    pub name: String,
}

/// 推测结果列表(NameInfoResultList)
#[derive(Debug, Serialize)]
pub struct NameInfoResultList {
    pub results: Vec<NameInfoResult>,
}

/// 姓名偏好与寓意解释(NameInfoResultExplanation)
#[derive(Debug, Serialize)]
pub struct NameInfoResultExplanation {
    pub explanation_wuxing: String,
    pub explanation_constellation: String,
    pub explanation_meaning: String,
}
