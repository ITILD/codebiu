//! 用户-模型绑定 DTO(对齐 Python module_rag/do/user_model.py)

use sea_orm::prelude::DateTimeWithTimeZone;
use serde::{Deserialize, Serialize};

use crate::do_::entity::user_model;

/// 模型类型编码(对齐 Python ModelType.value, module-ai 的 model_config.model_type 取值)
pub mod model_type {
    pub const CHAT: &str = "chat";
    pub const EMBEDDINGS: &str = "embeddings";
    pub const RERANK: &str = "rerank";
    pub const ASR: &str = "asr";
    pub const TTS: &str = "tts";
    pub const VAD: &str = "vad";
    pub const DENOISE: &str = "denoise";
}

/// 更新用户-模型绑定请求
///
/// 注意: serde 无法区分"未传"与"显式 null", 两者统一按解绑(None)处理,
/// 与 Python exclude_unset 语义存在偏差(已在模块报告注明)。
#[derive(Debug, Default, Deserialize)]
pub struct UserModelUpdate {
    #[serde(default)]
    pub chat_model_id: Option<String>,
    #[serde(default)]
    pub embedding_model_id: Option<String>,
    #[serde(default)]
    pub rerank_model_id: Option<String>,
    #[serde(default)]
    pub asr_model_id: Option<String>,
    #[serde(default)]
    pub tts_model_id: Option<String>,
    #[serde(default)]
    pub vad_model_id: Option<String>,
    #[serde(default)]
    pub denoise_model_id: Option<String>,
    #[serde(default)]
    pub fallback_disabled: Option<bool>,
}

/// 用户-模型绑定响应(未绑定时 id/created_at/updated_at 为空值)
#[derive(Debug, Serialize)]
pub struct UserModelResponse {
    pub id: String,
    pub user_id: String,
    pub chat_model_id: Option<String>,
    pub embedding_model_id: Option<String>,
    pub rerank_model_id: Option<String>,
    pub asr_model_id: Option<String>,
    pub tts_model_id: Option<String>,
    pub vad_model_id: Option<String>,
    pub denoise_model_id: Option<String>,
    pub fallback_disabled: bool,
    pub created_at: Option<DateTimeWithTimeZone>,
    pub updated_at: Option<DateTimeWithTimeZone>,
}

impl UserModelResponse {
    /// 空绑定响应(未落库, 跟随系统默认公共模型)
    pub fn empty(user_id: &str) -> Self {
        Self {
            id: String::new(),
            user_id: user_id.to_string(),
            chat_model_id: None,
            embedding_model_id: None,
            rerank_model_id: None,
            asr_model_id: None,
            tts_model_id: None,
            vad_model_id: None,
            denoise_model_id: None,
            fallback_disabled: false,
            created_at: None,
            updated_at: None,
        }
    }
}

impl From<user_model::Model> for UserModelResponse {
    fn from(m: user_model::Model) -> Self {
        Self {
            id: m.id,
            user_id: m.user_id,
            chat_model_id: m.chat_model_id,
            embedding_model_id: m.embedding_model_id,
            rerank_model_id: m.rerank_model_id,
            asr_model_id: m.asr_model_id,
            tts_model_id: m.tts_model_id,
            vad_model_id: m.vad_model_id,
            denoise_model_id: m.denoise_model_id,
            fallback_disabled: m.fallback_disabled,
            created_at: m.created_at,
            updated_at: Some(m.updated_at),
        }
    }
}

/// 模型解析结果(v4 4.3 兜底链可感知)
///
/// - fallback_used=true: 走了默认公共模型回退
/// - binding_unset=true: 用户本就未设置该类型模型(正常默认行为, 前端无需告警)
/// - fallback_used=true 且 binding_unset=false: 绑定失效, 数据流向已变化需提示
#[derive(Debug, Clone)]
pub struct ResolvedModel {
    pub model_id: Option<String>,
    pub fallback_used: bool,
    pub binding_unset: bool,
}
