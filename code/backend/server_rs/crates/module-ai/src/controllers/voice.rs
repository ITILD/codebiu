//! 语音控制器(对齐 Python controller/voice.py; 前缀 /voice)
//!
//! 降级约定: 语音引擎未在 Rust 服务实现, 所有端点完成基础请求校验(空音频/空文本)
//! 后统一返回业务错误 "语音引擎暂未在 Rust 服务实现"; WS /asr/stream 连接后发送关闭帧。

use axum::extract::ws::{CloseFrame, Message, WebSocket, WebSocketUpgrade};
use axum::extract::{Multipart, State};
use axum::response::Response;
use axum::routing::post;
use axum::{Json, Router};

use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::extract::AppJson;

use crate::do_::voice::{TTSRequest, VADResponse};
use crate::services::voice::VOICE_UNAVAILABLE;

/// 语音引擎未实现的统一业务错误
fn voice_unavailable() -> AppError {
    AppError::business(VOICE_UNAVAILABLE)
}

/// 从 multipart 中提取上传音频字节(空文件 400 "音频文件为空", 对齐 Python)
async fn parse_audio(multipart: Multipart) -> Result<Vec<u8>, AppError> {
    let mut audio: Option<Vec<u8>> = None;
    let mut multipart = multipart;
    while let Some(field) = multipart
        .next_field()
        .await
        .map_err(|e| AppError::validation(&["body", "form"], format!("表单解析失败: {e}")))?
    {
        if field.name().unwrap_or_default() == "audio" {
            let bytes = field
                .bytes()
                .await
                .map_err(|e| AppError::validation(&["body", "audio"], format!("音频读取失败: {e}")))?;
            audio = Some(bytes.to_vec());
        }
    }
    let audio = audio.unwrap_or_default();
    if audio.is_empty() {
        return Err(AppError::business("音频文件为空"));
    }
    Ok(audio)
}

/// POST /asr —— 语音识别(音频上传; 空文件 400, 其余统一未实现错误)
pub async fn asr_upload(
    _state: State<AppState>,
    multipart: Multipart,
) -> Result<Json<crate::do_::voice::ASRResponse>, AppError> {
    let _audio = parse_audio(multipart).await?;
    Err(voice_unavailable())
}

/// POST /tts/file —— 语音合成(返回完整音频文件; 空文本 400, 其余统一未实现错误)
pub async fn tts_file(
    _state: State<AppState>,
    AppJson(req): AppJson<TTSRequest>,
) -> Result<Response, AppError> {
    if req.text.trim().is_empty() {
        return Err(AppError::business("文本内容为空"));
    }
    Err(voice_unavailable())
}

/// POST /tts/stream —— 语音合成(流式返回 PCM; 空文本 400, 其余统一未实现错误)
pub async fn tts_stream(
    _state: State<AppState>,
    AppJson(req): AppJson<TTSRequest>,
) -> Result<Response, AppError> {
    if req.text.trim().is_empty() {
        return Err(AppError::business("文本内容为空"));
    }
    Err(voice_unavailable())
}

/// POST /vad —— 语音活动检测(空文件 400, 其余统一未实现错误)
pub async fn vad_detect(
    _state: State<AppState>,
    multipart: Multipart,
) -> Result<Json<VADResponse>, AppError> {
    let _audio = parse_audio(multipart).await?;
    Err(voice_unavailable())
}

/// POST /denoise —— 语音降噪(空文件 400, 其余统一未实现错误)
pub async fn denoise_audio(
    _state: State<AppState>,
    multipart: Multipart,
) -> Result<Response, AppError> {
    let _audio = parse_audio(multipart).await?;
    Err(voice_unavailable())
}

/// WS 连接处理: 接受连接后立即发送关闭帧(语音引擎未实现)
async fn handle_asr_stream(mut socket: WebSocket) {
    let frame = CloseFrame {
        code: axum::extract::ws::close_code::ERROR,
        reason: VOICE_UNAVAILABLE.into(),
    };
    let _ = socket.send(Message::Close(Some(frame))).await;
}

/// WS /asr/stream —— 麦克风实时流式语音识别(升级后立即发送关闭帧)
pub async fn asr_stream(ws: WebSocketUpgrade) -> Response {
    ws.on_upgrade(handle_asr_stream)
}

/// 语音子路由(nest 到 /voice 前缀)
pub fn router() -> Router<AppState> {
    Router::new()
        .route("/asr", post(asr_upload))
        .route("/asr/stream", post(asr_stream))
        .route("/tts/file", post(tts_file))
        .route("/tts/stream", post(tts_stream))
        .route("/vad", post(vad_detect))
        .route("/denoise", post(denoise_audio))
}
