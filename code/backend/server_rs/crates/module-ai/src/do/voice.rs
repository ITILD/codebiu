//! 语音 DTO(对齐 Python module_ai/do/voice.py)
//!
//! 降级约定: 语音各引擎(dashscope WS / sherpa 本地)未在 Rust 服务实现,
//! 全部 HTTP 端点返回 AppError::business("语音引擎暂未在 Rust 服务实现"),
//! WS /voice/asr/stream 连接后立即发送关闭帧; DTO 保留契约形状供前端对齐。

use serde::{Deserialize, Serialize};

/// 语音引擎方案: online(远程 API) / local(本机推理); 旧值 dashscope/sherpa/qwen 由 resolve_engine 归一化
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum VoiceEngine {
    Online,
    Local,
}

impl VoiceEngine {
    pub fn as_str(self) -> &'static str {
        match self {
            VoiceEngine::Online => "online",
            VoiceEngine::Local => "local",
        }
    }
}

/// 归一化 engine 字符串(旧值 dashscope→online, sherpa/qwen→local; 空值/无效返回 None)
pub fn normalize_engine(raw: Option<&str>) -> Option<VoiceEngine> {
    let raw = raw?.trim().to_lowercase();
    match raw.as_str() {
        "dashscope" => Some(VoiceEngine::Online),
        "sherpa" | "qwen" => Some(VoiceEngine::Local),
        "online" => Some(VoiceEngine::Online),
        "local" => Some(VoiceEngine::Local),
        _ => None,
    }
}

/// 解析 engine 参数并归一化(无效非空值回落 LOCAL, 对齐 Python resolve_engine)
pub fn resolve_engine(raw: Option<&str>) -> Option<VoiceEngine> {
    match normalize_engine(raw) {
        Some(e) => Some(e),
        None if raw.map(|r| !r.trim().is_empty()).unwrap_or(false) => Some(VoiceEngine::Local),
        None => None,
    }
}

/// 语音合成请求体(契约保留, Rust 侧端点统一返回未实现错误)
#[derive(Debug, Clone, Deserialize)]
pub struct TTSRequest {
    pub text: String,
    #[serde(default)]
    pub engine: Option<String>,
    #[serde(default)]
    pub speaker: i32,
    #[serde(default = "d_speed")]
    pub speed: f64,
    #[serde(default = "d_rate")]
    pub sample_rate: i32,
}

fn d_speed() -> f64 {
    1.0
}
fn d_rate() -> i32 {
    22050
}

/// 语音识别响应(契约保留)
#[derive(Debug, Clone, Serialize)]
pub struct ASRResponse {
    pub text: String,
    pub engine: VoiceEngine,
    pub elapsed: f64,
}

/// ASR 流式识别消息(WebSocket, 契约保留)
#[derive(Debug, Clone, Serialize)]
pub struct ASRStreamMessage {
    pub text: String,
    pub is_final: bool,
    pub engine: VoiceEngine,
}

/// VAD 检测响应(契约保留)
#[derive(Debug, Clone, Serialize)]
pub struct VADResponse {
    pub segments: Vec<serde_json::Value>,
    pub elapsed: f64,
}
