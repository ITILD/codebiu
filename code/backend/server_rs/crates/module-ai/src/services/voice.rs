//! 语音服务层(对齐 Python module_ai/service/voice.py 的接口面)
//!
//! 降级约定: 语音各引擎(dashscope 在线 WS / sherpa 本地 ONNX)未在 Rust 服务实现,
//! 所有方法统一返回业务错误, 由控制器透传给前端; DTO 层保留契约形状。

use common::utils::error::AppError;

/// 语音引擎未实现的统一错误文案
pub const VOICE_UNAVAILABLE: &str = "语音引擎暂未在 Rust 服务实现";

/// 语音识别(返回统一未实现错误)
pub async fn asr() -> Result<(), AppError> {
    Err(AppError::business(VOICE_UNAVAILABLE))
}

/// 语音合成(返回统一未实现错误)
pub async fn tts() -> Result<(), AppError> {
    Err(AppError::business(VOICE_UNAVAILABLE))
}

/// 语音活动检测(返回统一未实现错误)
pub async fn vad() -> Result<(), AppError> {
    Err(AppError::business(VOICE_UNAVAILABLE))
}

/// 语音降噪(返回统一未实现错误)
pub async fn denoise() -> Result<(), AppError> {
    Err(AppError::business(VOICE_UNAVAILABLE))
}
