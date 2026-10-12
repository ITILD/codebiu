//! 语音服务层(对齐 Python module_ai/service/voice.py 的接口面)
//!
//! 实现范围(online 方案, DashScope HTTP 协议):
//! - ASR 整段识别: multimodal-generation 接口, 音频 base64 内联上传
//! - TTS 文件合成: SpeechSynthesizer 接口, 返回完整 WAV
//! - TTS 流式合成: HTTP 整段合成 + WAV 解码 PCM 切片(契约 audio/pcm 一致)
//! - ASR WS 伪流式: 缓冲 PCM 定长切片后台识别(对齐 Python PseudoStreamSession)
//!
//! 未实现降级(与 Python 契约一致): local 方案(sherpa onnx)/VAD/降噪。

use std::time::Instant;

use base64::Engine as _;
use serde_json::{json, Value};

use common::runtime::AppState;
use common::utils::error::AppError;

use crate::dao::model_config as mc_dao;
use crate::do_::entity::model_config as entity;
use crate::do_::voice::VoiceEngine;

/// 本地方案(sherpa onnx)与 VAD/降噪的统一未实现文案
pub const VOICE_UNAVAILABLE: &str = "本地语音引擎(sherpa onnx)暂未在 Rust 服务实现, 请使用在线(online)方案";

/// DashScope 默认端点(配置缺失时回落)
const DASHSCOPE_ASR_URL: &str =
    "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation";
const DASHSCOPE_TTS_URL: &str =
    "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer";
/// 默认音色(CosyVoice 系)
const DEFAULT_VOICE: &str = "longxiaochun";
/// TTS 服务端支持的采样率档位
const TTS_SAMPLE_RATES: [i64; 6] = [8000, 16000, 22050, 24000, 44100, 48000];

/// 语音引擎运行配置(model_config 行 + extra 展平)
#[derive(Debug, Clone)]
pub struct VoiceConf {
    pub model: String,
    pub url: String,
    pub api_key: String,
    pub voice: String,
    pub language: Option<String>,
    pub enable_itn: Option<bool>,
    pub rate: f64,
    pub timeout: f64,
}

/// 语音识别结果
pub struct AsrOutput {
    pub text: String,
    pub engine: VoiceEngine,
    pub elapsed: f64,
}

/// 语音合成结果(文件口径: WAV 字节)
pub struct TtsOutput {
    pub wav: Vec<u8>,
    pub engine: VoiceEngine,
}

/// 引擎解析 + 配置展平
///
/// 对齐 Python _resolve_engine: 指定 engine 时按 server_type 精确匹配,
/// 未指定时取该类型第一条配置; 无配置回落 local(未实现提示)。
pub async fn resolve_conf(
    state: &AppState,
    model_type: &str,
    engine: Option<VoiceEngine>,
) -> Result<(VoiceConf, VoiceEngine), AppError> {
    let config = match engine {
        Some(e) => {
            mc_dao::get_first_by_type(&state.db, model_type, Some(e.as_str())).await?
        }
        None => mc_dao::get_first_by_type(&state.db, model_type, None).await?,
    };
    let Some(config) = config else {
        return Err(AppError::business(match engine {
            Some(e) => format!("未配置 server_type={} 的 {model_type} 模型, 请先在模型管理中添加", e.as_str()),
            None => format!("未配置 {model_type} 模型, 请先在模型管理中添加或由管理员配置公共默认模型"),
        }));
    };
    let effective = match config.server_type.as_str() {
        "online" | "dashscope" => VoiceEngine::Online,
        _ => VoiceEngine::Local,
    };
    if effective != VoiceEngine::Online {
        return Err(AppError::business(
            "本地语音引擎(sherpa onnx)暂未在 Rust 服务实现, 请在模型管理中配置在线(online)方案",
        ));
    }
    Ok((flatten_conf(&config), effective))
}

/// model_config 行 → 运行配置(extra 键展平, 对齐 Python _engine_conf)
fn flatten_conf(config: &entity::Model) -> VoiceConf {
    let extra = config.extra.clone().unwrap_or(Value::Null);
    let s = |key: &str| {
        extra
            .get(key)
            .and_then(Value::as_str)
            .map(str::to_string)
            .filter(|v| !v.is_empty())
    };
    VoiceConf {
        model: if config.model.is_empty() {
            "qwen3-asr-flash".to_string()
        } else {
            config.model.clone()
        },
        url: config
            .url
            .clone()
            .filter(|u| !u.is_empty())
            .unwrap_or_else(|| DASHSCOPE_ASR_URL.to_string()),
        api_key: config.api_key.clone().unwrap_or_default(),
        voice: s("voice").unwrap_or_else(|| DEFAULT_VOICE.to_string()),
        language: s("language"),
        enable_itn: extra.get("enable_itn").and_then(Value::as_bool),
        rate: extra
            .get("rate")
            .and_then(Value::as_f64)
            .unwrap_or(1.0)
            .clamp(0.5, 2.0),
        timeout: extra
            .get("timeout")
            .and_then(Value::as_f64)
            .or(config.timeout.map(|t| t as f64))
            .unwrap_or(60.0),
    }
}

/// 音频魔数 → MIME(构造 Data URL 用)
fn detect_audio_mime(audio: &[u8]) -> &'static str {
    if audio.starts_with(b"ID3")
        || audio.starts_with(&[0xff, 0xfb])
        || audio.starts_with(&[0xff, 0xf3])
        || audio.starts_with(&[0xff, 0xf2])
    {
        "audio/mpeg"
    } else if audio.starts_with(b"OggS") {
        "audio/ogg"
    } else if audio.starts_with(b"fLaC") {
        "audio/flac"
    } else if audio.starts_with(b"RIFF") {
        "audio/wav"
    } else {
        "audio/wav"
    }
}

/// 语音识别(整段上传, 引擎解析 + DashScope multimodal-generation 协议)
pub async fn asr(
    state: &AppState,
    audio: Vec<u8>,
    engine: Option<VoiceEngine>,
) -> Result<AsrOutput, AppError> {
    let start = Instant::now();
    let (conf, engine) = resolve_conf(state, "asr", engine).await?;
    let text = asr_with_conf(state, &conf, audio).await?;
    Ok(AsrOutput {
        text,
        engine,
        elapsed: (start.elapsed().as_secs_f64() * 1000.0).round() / 1000.0,
    })
}

/// 按已解析配置执行识别(WS 伪流式切片复用, 避免每片重复查库)
pub async fn asr_with_conf(
    state: &AppState,
    conf: &VoiceConf,
    audio: Vec<u8>,
) -> Result<String, AppError> {
    if conf.api_key.trim().is_empty() {
        return Err(AppError::business(
            "DashScope ASR 缺少 api_key: 请在模型配置中填写百炼 API Key",
        ));
    }
    // base64 Data URL 内联上传(编码后需 <10MB)
    let data_uri = format!(
        "data:{};base64,{}",
        detect_audio_mime(&audio),
        base64::engine::general_purpose::STANDARD.encode(&audio)
    );
    let mut payload = json!({
        "model": conf.model,
        "input": {
            "messages": [
                { "role": "user", "content": [ { "audio": data_uri } ] },
            ],
        },
    });
    // 语种提示/ITN 为可选参数
    let mut asr_options = serde_json::Map::new();
    if let Some(lang) = &conf.language {
        asr_options.insert("language".into(), json!(lang));
    }
    if let Some(itn) = conf.enable_itn {
        asr_options.insert("enable_itn".into(), json!(itn));
    }
    if !asr_options.is_empty() {
        payload["parameters"] = json!({ "asr_options": asr_options });
    }
    let resp = state
        .http
        .post(&conf.url)
        .header("Authorization", format!("Bearer {}", conf.api_key))
        .timeout(std::time::Duration::from_secs_f64(conf.timeout.max(1.0)))
        .json(&payload)
        .send()
        .await
        .map_err(|e| AppError::business(format!("DashScope ASR 请求失败: {e}")))?;
    let status = resp.status();
    let body: Value = resp
        .json()
        .await
        .map_err(|e| AppError::business(format!("DashScope ASR 响应解析失败: {e}")))?;
    if !status.is_success() {
        return Err(AppError::business(format!(
            "DashScope ASR 请求失败({status}): {}",
            serde_json::to_string(&body).unwrap_or_default()
        )));
    }
    let text = body
        .get("output")
        .and_then(|o| o.get("choices"))
        .and_then(Value::as_array)
        .and_then(|choices| {
            choices.iter().find_map(|choice| {
                choice
                    .get("message")
                    .and_then(|m| m.get("content"))
                    .and_then(Value::as_array)
                    .and_then(|content| {
                        content.iter().find_map(|item| {
                            item.get("text").and_then(Value::as_str).map(str::to_string)
                        })
                    })
            })
        })
        .map(|t| t.trim().to_string())
        .unwrap_or_default();
    if text.is_empty() {
        return Err(AppError::business(format!(
            "DashScope ASR 未返回识别文本: {}",
            serde_json::to_string(&body).unwrap_or_default()
        )));
    }
    Ok(text)
}

/// 请求采样率映射到 TTS 服务端支持的最近档位
fn nearest_sample_rate(sample_rate: i64) -> i64 {
    if TTS_SAMPLE_RATES.contains(&sample_rate) {
        return sample_rate;
    }
    *TTS_SAMPLE_RATES
        .iter()
        .min_by_key(|sr| sr.abs_diff(sample_rate))
        .unwrap_or(&22050)
}

/// 语音合成(DashScope SpeechSynthesizer 协议, 返回完整 WAV)
///
/// 对齐 Python DashscopeTTS._synthesize_wav: 非流式调用, 音频以 URL(24h 有效)
/// 或 base64 data 返回, 引擎自动下载。
pub async fn tts(
    state: &AppState,
    text: &str,
    speed: f64,
    sample_rate: i64,
    engine: Option<VoiceEngine>,
) -> Result<TtsOutput, AppError> {
    let (mut conf, engine) = resolve_conf(state, "tts", engine).await?;
    if conf.api_key.trim().is_empty() {
        return Err(AppError::business(
            "DashScope TTS 缺少 api_key: 请在模型配置中填写百炼 API Key",
        ));
    }
    // TTS 默认端点与 ASR 不同, 配置 URL 来自 tts 专属配置行
    if conf.url == DASHSCOPE_ASR_URL {
        conf.url = DASHSCOPE_TTS_URL.to_string();
    }
    let payload = json!({
        "model": conf.model,
        "input": {
            "text": text,
            "voice": conf.voice,
            "format": "wav",
            "sample_rate": nearest_sample_rate(sample_rate),
            "rate": speed.clamp(0.5, 2.0),
        },
    });
    let http = &state.http;
    let resp = http
        .post(&conf.url)
        .header("Authorization", format!("Bearer {}", conf.api_key))
        .timeout(std::time::Duration::from_secs_f64(conf.timeout.max(1.0)))
        .json(&payload)
        .send()
        .await
        .map_err(|e| AppError::business(format!("DashScope TTS 请求失败: {e}")))?;
    let status = resp.status();
    let body: Value = resp
        .json()
        .await
        .map_err(|e| AppError::business(format!("DashScope TTS 响应解析失败: {e}")))?;
    if !status.is_success() {
        return Err(AppError::business(format!(
            "DashScope TTS 请求失败({status}): {}",
            serde_json::to_string(&body).unwrap_or_default()
        )));
    }
    let audio = body
        .get("output")
        .and_then(|o| o.get("audio"))
        .cloned()
        .unwrap_or(Value::Null);
    // 响应二选一: base64 data 直接解码 / URL 下载
    let wav = if let Some(data) = audio.get("data").and_then(Value::as_str) {
        base64::engine::general_purpose::STANDARD
            .decode(data)
            .map_err(|e| AppError::business(format!("DashScope TTS 音频解码失败: {e}")))?
    } else if let Some(url) = audio.get("url").and_then(Value::as_str) {
        let file_resp = http
            .get(url)
            .timeout(std::time::Duration::from_secs_f64(conf.timeout.max(1.0)))
            .send()
            .await
            .map_err(|e| AppError::business(format!("DashScope TTS 音频下载失败: {e}")))?;
        let status = file_resp.status();
        let bytes = file_resp
            .bytes()
            .await
            .map_err(|e| AppError::business(format!("DashScope TTS 音频下载失败: {e}")))?;
        if !status.is_success() {
            return Err(AppError::business(format!(
                "DashScope TTS 音频下载失败({status})"
            )));
        }
        bytes.to_vec()
    } else {
        return Err(AppError::business(format!(
            "DashScope TTS 未返回音频: {}",
            serde_json::to_string(&body).unwrap_or_default()
        )));
    };
    Ok(TtsOutput { wav, engine })
}

/// 极简 WAV 解析: 提取 PCM 数据字节(16bit PCM/float 转换不做, DashScope 返回 16bit)
///
/// 返回 (pcm_bytes, 实际采样率); 非 WAV 输入原样返回(按调用方采样率)。
pub fn wav_to_pcm(wav: &[u8], fallback_rate: i64) -> (Vec<u8>, i64) {
    // RIFF 头: "RIFF" + size + "WAVE", 后续为 chunk 流("fmt "/"data")
    if wav.len() < 44 || &wav[0..4] != b"RIFF" || &wav[8..12] != b"WAVE" {
        return (wav.to_vec(), fallback_rate);
    }
    let mut sample_rate = fallback_rate;
    let mut pcm: Option<&[u8]> = None;
    let mut pos = 12usize;
    while pos + 8 <= wav.len() {
        let chunk_id = &wav[pos..pos + 4];
        let chunk_size = u32::from_le_bytes([
            wav[pos + 4],
            wav[pos + 5],
            wav[pos + 6],
            wav[pos + 7],
        ]) as usize;
        let data_start = pos + 8;
        let data_end = (data_start + chunk_size).min(wav.len());
        match chunk_id {
            b"fmt " => {
                // fmt 块: audio_format(2) + channels(2) + sample_rate(4) + ...
                if data_end >= data_start + 8 {
                    sample_rate = u32::from_le_bytes([
                        wav[data_start + 4],
                        wav[data_start + 5],
                        wav[data_start + 6],
                        wav[data_start + 7],
                    ]) as i64;
                }
            }
            b"data" => {
                pcm = Some(&wav[data_start..data_end]);
            }
            _ => {}
        }
        pos = data_start + chunk_size + (chunk_size & 1); // 块按 2 字节对齐
    }
    match pcm {
        Some(p) => (p.to_vec(), sample_rate),
        None => (wav.to_vec(), fallback_rate),
    }
}

/// PCM → WAV 封装(16bit 单声道, 降噪/VAD 响应用)
#[allow(dead_code)]
pub fn pcm_to_wav(pcm: &[u8], sample_rate: i32, channels: i16) -> Vec<u8> {
    let data_len = pcm.len() as u32;
    let byte_rate = (sample_rate as u32) * (channels as u32) * 2;
    let mut out = Vec::with_capacity(44 + pcm.len());
    out.extend_from_slice(b"RIFF");
    out.extend_from_slice(&(36 + data_len).to_le_bytes());
    out.extend_from_slice(b"WAVE");
    out.extend_from_slice(b"fmt ");
    out.extend_from_slice(&16u32.to_le_bytes());
    out.extend_from_slice(&1i16.to_le_bytes()); // PCM 格式
    out.extend_from_slice(&channels.to_le_bytes());
    out.extend_from_slice(&(sample_rate as u32).to_le_bytes());
    out.extend_from_slice(&byte_rate.to_le_bytes());
    out.extend_from_slice(&((channels as u16) * 2).to_le_bytes()); // 块对齐
    out.extend_from_slice(&16i16.to_le_bytes()); // 位深
    out.extend_from_slice(b"data");
    out.extend_from_slice(&data_len.to_le_bytes());
    out.extend_from_slice(pcm);
    out
}
