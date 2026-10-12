//! 语音控制器(对齐 Python controller/voice.py; 前缀 /voice)
//!
//! 实现范围: ASR 整段识别 / TTS 文件合成 / TTS 流式合成(HTTP 合成 + PCM 切片) /
//! ASR WS 伪流式(缓冲 PCM 定长切片后台识别, 前端协议: 二进制 PCM 帧 + Text "EOS" 结束);
//! VAD/降噪(本地 sherpa onnx)保留未实现降级提示。

use axum::body::Body;
use axum::extract::ws::{Message, WebSocket, WebSocketUpgrade};
use axum::extract::{Multipart, Query, State};
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use futures::stream;
use serde::Deserialize;

use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::extract::AppJson;

use crate::do_::voice::{ASRResponse, ASRStreamMessage, TTSRequest, VADResponse, VoiceEngine};
use crate::services::voice::{self as svc, VOICE_UNAVAILABLE};

/// 语音活动检测/降噪的统一未实现错误(本地 sherpa onnx 方案)
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

/// POST /asr?engine=online —— 语音识别(multipart 音频 + query engine)
pub async fn asr_upload_with_engine(
    State(state): State<AppState>,
    Query(q): Query<EngineQuery>,
    multipart: Multipart,
) -> Result<Json<ASRResponse>, AppError> {
    let audio = parse_audio(multipart).await?;
    let engine = crate::do_::voice::resolve_engine(q.engine.as_deref());
    let out = svc::asr(&state, audio, engine).await?;
    Ok(Json(ASRResponse {
        text: out.text,
        engine: out.engine,
        elapsed: out.elapsed,
    }))
}

/// engine 查询参数
#[derive(Debug, Default, Deserialize)]
pub struct EngineQuery {
    pub engine: Option<String>,
}

/// POST /tts/file —— 语音合成(返回完整 WAV 音频文件)
pub async fn tts_file(
    State(state): State<AppState>,
    AppJson(req): AppJson<TTSRequest>,
) -> Result<Response, AppError> {
    if req.text.trim().is_empty() {
        return Err(AppError::business("文本内容为空"));
    }
    let engine = crate::do_::voice::resolve_engine(req.engine.as_deref());
    let out = svc::tts(&state, &req.text, req.speed, req.sample_rate as i64, engine).await?;
    Ok((
        StatusCode::OK,
        [("Content-Type", "audio/wav")],
        out.wav,
    )
        .into_response())
}

/// POST /tts/stream —— 语音合成(流式返回 PCM; HTTP 整段合成后按块下发)
pub async fn tts_stream(
    State(state): State<AppState>,
    AppJson(req): AppJson<TTSRequest>,
) -> Result<Response, AppError> {
    if req.text.trim().is_empty() {
        return Err(AppError::business("文本内容为空"));
    }
    let engine = crate::do_::voice::resolve_engine(req.engine.as_deref());
    let out = svc::tts(&state, &req.text, req.speed, req.sample_rate as i64, engine).await?;
    // WAV → PCM(按实际采样率下发, 前端经响应头读取)
    let (pcm, rate) = svc::wav_to_pcm(&out.wav, req.sample_rate as i64);
    let chunk_size = 4096usize;
    let chunks: Vec<Result<Vec<u8>, std::io::Error>> = pcm
        .chunks(chunk_size)
        .map(|c| Ok(c.to_vec()))
        .collect();
    let body = Body::from_stream(stream::iter(chunks));
    Ok((
        StatusCode::OK,
        [
            ("Content-Type", "audio/pcm".to_string()),
            ("X-Sample-Rate", rate.to_string()),
        ],
        body,
    )
        .into_response())
}

/// POST /vad —— 语音活动检测(本地方案未实现)
pub async fn vad_detect(
    _state: State<AppState>,
    multipart: Multipart,
) -> Result<Json<VADResponse>, AppError> {
    let _audio = parse_audio(multipart).await?;
    Err(voice_unavailable())
}

/// POST /denoise —— 语音降噪(本地方案未实现)
pub async fn denoise_audio(
    _state: State<AppState>,
    multipart: Multipart,
) -> Result<Response, AppError> {
    let _audio = parse_audio(multipart).await?;
    Err(voice_unavailable())
}

/// WS 连接参数(engine; sample_rate 当前固定 16k, 字段保留以兼容前端传参)
#[derive(Debug, Default, Deserialize)]
pub struct WsQuery {
    pub engine: Option<String>,
    #[serde(default = "d_sample_rate")]
    #[allow(dead_code)]
    pub sample_rate: i32,
}

fn d_sample_rate() -> i32 {
    16000
}

/// WS 下行 JSON 帧(ASRStreamMessage 序列化)
fn json_frame(msg: &ASRStreamMessage) -> Message {
    Message::Text(serde_json::to_string(msg).unwrap_or_default().into())
}

/// 伪流式切片阈值: 5 秒 16k int16 单声道(对齐 Python PseudoStreamSession 定长切片)
const PSEUDO_CHUNK_SECONDS: f64 = 5.0;

/// WS /asr/stream —— 麦克风实时流式语音识别(伪流式)
///
/// 协议: 上行二进制帧为 16k 单声道 int16 PCM; 上行 Text "EOS" 表示结束;
/// 下行 JSON 帧 ASRStreamMessage{text, is_final, engine}(切片识别完成后推送累计文本)。
async fn handle_asr_stream(state: AppState, engine: VoiceEngine, mut socket: WebSocket) {
    // 预解析引擎配置(每切片复用; 失败发错误说明后关闭)
    let conf = match svc::resolve_conf(&state, "asr", Some(engine)).await {
        Ok((conf, _)) => conf,
        Err(e) => {
            let _ = socket
                .send(Message::Text(
                    serde_json::json!({
                        "text": e.to_string(),
                        "is_final": true,
                        "engine": engine.as_str(),
                    })
                    .to_string()
                    .into(),
                ))
                .await;
            let _ = socket.send(Message::Close(None)).await;
            return;
        }
    };
    let sample_rate = 16000i64;
    let chunk_bytes = (sample_rate as f64 * PSEUDO_CHUNK_SECONDS) as usize * 2;
    let mut buffer: Vec<u8> = Vec::new();
    let mut text = String::new();
    // 切片识别结果通道(后台任务完成后推送); EOS 后置 None 关闭通道
    let (tx, mut rx) = tokio::sync::mpsc::channel::<String>(8);
    let mut tx_opt: Option<tokio::sync::mpsc::Sender<String>> = Some(tx);

    loop {
        tokio::select! {
            // 后台切片识别完成 → 推送累计文本(中间结果)
            piece = rx.recv() => {
                match piece {
                    Some(p) if !p.is_empty() => {
                        text.push_str(&p);
                        let msg = ASRStreamMessage {
                            text: text.clone(),
                            is_final: false,
                            engine,
                        };
                        if socket.send(json_frame(&msg)).await.is_err() {
                            break;
                        }
                    }
                    None => {
                        // 全部识别任务完成(EOS 收尾): 推送最终文本后关闭
                        let msg = ASRStreamMessage {
                            text: text.clone(),
                            is_final: true,
                            engine,
                        };
                        let _ = socket.send(json_frame(&msg)).await;
                        let _ = socket.send(Message::Close(None)).await;
                        break;
                    }
                    _ => {}
                }
            }
            // 客户端上行帧
            msg = socket.recv() => {
                let Some(Ok(msg)) = msg else { break };
                match msg {
                    Message::Binary(data) => {
                        buffer.extend_from_slice(&data);
                        while buffer.len() >= chunk_bytes {
                            let chunk: Vec<u8> = buffer.drain(..chunk_bytes).collect();
                            if let Some(t) = tx_opt.as_ref() {
                                spawn_slice(&state, &conf, chunk, t.clone());
                            }
                        }
                    }
                    Message::Text(t) if t.trim() == "EOS" => {
                        // 结束: 提交剩余缓冲并等待全部切片识别完成(通道关闭后 rx 收 None)
                        if !buffer.is_empty() {
                            let chunk: Vec<u8> = std::mem::take(&mut buffer);
                            if let Some(t) = tx_opt.take() {
                                spawn_slice(&state, &conf, chunk, t.clone());
                            }
                        } else {
                            tx_opt = None;
                        }
                    }
                    Message::Close(_) => {
                        // 客户端直接关闭: 尽力冲刷(不等剩余识别)
                        let msg = ASRStreamMessage {
                            text: text.clone(),
                            is_final: true,
                            engine,
                        };
                        let _ = socket.send(json_frame(&msg)).await;
                        break;
                    }
                    _ => {}
                }
            }
        }
    }
}

/// 提交一个 PCM 切片到后台识别(PCM → WAV 封装 → DashScope; 失败返回空串不中断)
fn spawn_slice(
    state: &AppState,
    conf: &svc::VoiceConf,
    pcm: Vec<u8>,
    tx: tokio::sync::mpsc::Sender<String>,
) {
    let state = state.clone();
    let conf = conf.clone();
    tokio::spawn(async move {
        // PCM int16 → WAV 封装(识别接口要求完整音频容器)
        let wav = svc::pcm_to_wav(&pcm, 16000, 1);
        match svc::asr_with_conf(&state, &conf, wav).await {
            Ok(piece) => {
                let _ = tx.send(piece).await;
            }
            Err(e) => {
                tracing::warn!("伪流式切片识别失败: {e}");
            }
        }
    });
}

/// WS /asr/stream —— 升级入口(query 参数: engine/sample_rate)
pub async fn asr_stream(
    State(state): State<AppState>,
    Query(q): Query<WsQuery>,
    ws: WebSocketUpgrade,
) -> Response {
    let engine = crate::do_::voice::resolve_engine(q.engine.as_deref())
        .unwrap_or(VoiceEngine::Online);
    ws.on_upgrade(move |socket| handle_asr_stream(state, engine, socket))
}

/// 语音子路由(nest 到 /voice 前缀)
pub fn router() -> Router<AppState> {
    Router::new()
        .route("/asr", post(asr_upload_with_engine))
        .route("/asr/stream", get(asr_stream))
        .route("/tts/file", post(tts_file))
        .route("/tts/stream", post(tts_stream))
        .route("/vad", post(vad_detect))
        .route("/denoise", post(denoise_audio))
}
