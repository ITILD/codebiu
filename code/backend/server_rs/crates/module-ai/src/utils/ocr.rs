//! DashScope 在线 OCR 引擎(等价 Python utils/ocr/dashscope.py)
//!
//! 通过 DashScope 多模态接口调用 qwen-vl-ocr 系在线模型识别图片文字,
//! 图片以 base64 Data URL 内联上传, 返回整图纯文本(无坐标框)。
//!
//! Rust 侧无 cv2/numpy 依赖: 图片按原始字节做魔数嗅探封装 Data URL 上传,
//! 宽高从文件头解析(PNG/JPEG/GIF/BMP; 无法识别时按 0 处理, 结果框退化为点)。
//!
//! 结果结构与本地 paddle 流水线对齐: `{"ts": {...}, "results": [{box, text, score}]}`,
//! 在线结果 box 为整图矩形坐标列表(score 恒为 1.0)。
//!
//! 降级约定: 本地 ONNX OCR(Paddle) 未在 Rust 服务实现, 由服务层拦截并提示使用 online 引擎。

use std::time::{Duration, Instant};

use base64::Engine as _;
use base64::engine::general_purpose::STANDARD as BASE64;
use serde_json::{json, Value};

use common::utils::error::AppError;

/// DashScope 同步多模态生成接口(OCR)
const DASHSCOPE_OCR_URL: &str =
    "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation";
/// 默认请求超时(秒)
const DEFAULT_TIMEOUT: u64 = 60;
/// 默认 OCR 指令(qwen-vl-ocr 系模型专用提示)
const DEFAULT_PROMPT: &str = "Read all the text in this image.";

/// 阿里云在线 OCR 引擎(qwen-vl-ocr, 整图文本识别)
pub struct DashscopeOcr {
    model: String,
    url: String,
    api_key: String,
    prompt: String,
    timeout: u64,
}

impl DashscopeOcr {
    /// 从模型配置映射构建引擎(model/url/api_key/extra(prompt/timeout)); api_key 缺失报业务错误
    pub fn from_conf(conf: &Value) -> Result<Self, AppError> {
        let api_key = conf
            .get("api_key")
            .and_then(Value::as_str)
            .unwrap_or("")
            .trim()
            .to_string();
        if api_key.is_empty() {
            return Err(AppError::business(
                "DashScope OCR 缺少 api_key: 请在模型配置中填写百炼 API Key",
            ));
        }
        Ok(Self {
            model: conf
                .get("model")
                .and_then(Value::as_str)
                .filter(|s| !s.trim().is_empty())
                .unwrap_or("qwen-vl-ocr-latest")
                .to_string(),
            url: conf
                .get("url")
                .and_then(Value::as_str)
                .map(str::trim)
                .filter(|s| !s.is_empty())
                .unwrap_or(DASHSCOPE_OCR_URL)
                .to_string(),
            api_key,
            prompt: conf
                .get("prompt")
                .and_then(Value::as_str)
                .filter(|s| !s.trim().is_empty())
                .unwrap_or(DEFAULT_PROMPT)
                .to_string(),
            timeout: conf
                .get("timeout")
                .and_then(Value::as_u64)
                .filter(|t| *t > 0)
                .unwrap_or(DEFAULT_TIMEOUT),
        })
    }

    /// 上传图片识别文字, 返回与本地流水线同构的结果
    ///
    /// 返回: `{"ts": {"total": 秒}, "results": [{"box", "text", "score"}], "engine": "dashscope"}`
    pub async fn recognize(&self, http: &reqwest::Client, image: &[u8]) -> Result<Value, AppError> {
        // 宽高从文件头嗅探(无法识别按 0 处理), box 为整图矩形
        let (width, height) = image_size(image);
        let mime = sniff_mime(image);
        let data_uri = format!("data:{mime};base64,{}", BASE64.encode(image));
        let payload = json!({
            "model": self.model,
            "input": {
                "messages": [{
                    "role": "user",
                    "content": [
                        {"image": data_uri},
                        {"text": self.prompt},
                    ],
                }],
            },
        });
        let start = Instant::now();
        let resp = http
            .post(&self.url)
            .bearer_auth(&self.api_key)
            .json(&payload)
            .timeout(Duration::from_secs(self.timeout))
            .send()
            .await
            .map_err(|e| AppError::internal(format!("DashScope OCR 请求失败: {e}")))?;
        let status = resp.status();
        let body = resp.text().await.unwrap_or_default();
        if status.is_client_error() || status.is_server_error() {
            return Err(AppError::internal(format!(
                "DashScope OCR 请求失败({}): {}",
                status.as_u16(),
                super::truncate_body(&body)
            )));
        }
        let parsed: Value = serde_json::from_str(&body)
            .map_err(|e| AppError::internal(format!("DashScope OCR 响应解析失败: {e}")))?;
        let text = parse_ocr_text(&parsed).ok_or_else(|| {
            AppError::internal(format!(
                "DashScope OCR 未返回识别文本: {}",
                super::truncate_body(&body)
            ))
        })?;
        let elapsed = (start.elapsed().as_secs_f64() * 1000.0).round() / 1000.0;
        Ok(json!({
            "ts": {"total": elapsed},
            "results": [{
                "box": [[0, 0], [width, 0], [width, height], [0, height]],
                "text": text,
                "score": 1.0,
            }],
            "engine": "dashscope",
        }))
    }
}

/// 解析响应中的识别文本(output.choices[].message.content, 兼容 dict/str/纯字符串形态)
fn parse_ocr_text(payload: &Value) -> Option<String> {
    let choices = payload.pointer("/output/choices")?.as_array()?;
    for choice in choices {
        let Some(message) = choice.get("message") else {
            continue;
        };
        match message.get("content") {
            // content 为纯字符串的响应形态
            Some(Value::String(s)) => {
                let t = s.trim();
                if !t.is_empty() {
                    return Some(t.to_string());
                }
            }
            // content 为分段数组: {text: ...} 或裸字符串
            Some(Value::Array(items)) => {
                for item in items {
                    match item {
                        Value::String(s) => {
                            let t = s.trim();
                            if !t.is_empty() {
                                return Some(t.to_string());
                            }
                        }
                        Value::Object(_) => {
                            if let Some(t) = item.get("text").and_then(Value::as_str) {
                                let t = t.trim();
                                if !t.is_empty() {
                                    return Some(t.to_string());
                                }
                            }
                        }
                        _ => {}
                    }
                }
            }
            _ => {}
        }
    }
    None
}

/// 按魔数嗅探图片 MIME(无法识别时 application/octet-stream)
fn sniff_mime(bytes: &[u8]) -> &'static str {
    if bytes.starts_with(&[0xFF, 0xD8, 0xFF]) {
        "image/jpeg"
    } else if bytes.starts_with(&[0x89, b'P', b'N', b'G']) {
        "image/png"
    } else if bytes.starts_with(b"GIF8") {
        "image/gif"
    } else if bytes.starts_with(b"BM") {
        "image/bmp"
    } else if bytes.len() >= 12 && bytes.starts_with(b"RIFF") && &bytes[8..12] == b"WEBP" {
        "image/webp"
    } else {
        "application/octet-stream"
    }
}

/// 从图片文件头解析宽高(PNG/JPEG/GIF/BMP; webp 等未支持格式返回 (0, 0))
fn image_size(bytes: &[u8]) -> (u32, u32) {
    // PNG: 固定签名 + IHDR, 宽高位于偏移 16/20(大端)
    if bytes.len() >= 24 && bytes.starts_with(&[0x89, b'P', b'N', b'G']) {
        let w = u32::from_be_bytes(bytes[16..20].try_into().expect("PNG 宽度切片合法"));
        let h = u32::from_be_bytes(bytes[20..24].try_into().expect("PNG 高度切片合法"));
        return (w, h);
    }
    // GIF: 逻辑屏幕宽高位于偏移 6/8(小端)
    if bytes.len() >= 10 && bytes.starts_with(b"GIF8") {
        let w = u16::from_le_bytes(bytes[6..8].try_into().expect("GIF 宽度切片合法")) as u32;
        let h = u16::from_le_bytes(bytes[8..10].try_into().expect("GIF 高度切片合法")) as u32;
        return (w, h);
    }
    // BMP: DIB 头宽高位于偏移 18/22(小端有符号, 高度可能为负)
    if bytes.len() >= 26 && bytes.starts_with(b"BM") {
        let w = i32::from_le_bytes(bytes[18..22].try_into().expect("BMP 宽度切片合法"));
        let h = i32::from_le_bytes(bytes[22..26].try_into().expect("BMP 高度切片合法"));
        return (w.unsigned_abs(), h.unsigned_abs());
    }
    // JPEG: 扫描段标记定位 SOFn(0xC0~0xCF 排除 C4/C8/CC), 高度在标记后 +5, 宽度 +7(大端)
    if bytes.len() > 4 && bytes[0] == 0xFF && bytes[1] == 0xD8 {
        let mut pos = 2usize;
        while pos + 4 <= bytes.len() {
            if bytes[pos] != 0xFF {
                pos += 1;
                continue;
            }
            let marker = bytes[pos + 1];
            if marker == 0xFF {
                // 填充字节, 前进一位重新对齐
                pos += 1;
                continue;
            }
            if (0xC0..=0xCF).contains(&marker) && !matches!(marker, 0xC4 | 0xC8 | 0xCC) {
                if pos + 9 <= bytes.len() {
                    let h =
                        u16::from_be_bytes(bytes[pos + 5..pos + 7].try_into().expect("JPEG 高度切片合法"))
                            as u32;
                    let w =
                        u16::from_be_bytes(bytes[pos + 7..pos + 9].try_into().expect("JPEG 宽度切片合法"))
                            as u32;
                    return (w, h);
                }
                break;
            }
            // 其余段按段长跳过(段长含长度字段自身 2 字节, 不含标记)
            let seg_len =
                u16::from_be_bytes(bytes[pos + 2..pos + 4].try_into().expect("JPEG 段长切片合法")) as usize;
            pos += 2 + seg_len;
        }
        return (0, 0);
    }
    (0, 0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn png宽高解析() {
        // 最小 PNG 头: 签名(8) + IHDR 长度(4) + "IHDR"(4) + 宽高(8)
        let mut png = vec![0x89u8, b'P', b'N', b'G', 0x0D, 0x0A, 0x1A, 0x0A, 0, 0, 0, 0x0D, b'I', b'H', b'D', b'R'];
        png.extend_from_slice(&16u32.to_be_bytes());
        png.extend_from_slice(&32u32.to_be_bytes());
        assert_eq!(image_size(&png), (16, 32));
    }

    #[test]
    fn jpeg_mime嗅探与尺寸兜底() {
        assert_eq!(sniff_mime(&[0xFF, 0xD8, 0xFF, 0xE0]), "image/jpeg");
        assert_eq!(sniff_mime(b"not-an-image"), "application/octet-stream");
        assert_eq!(image_size(b"not-an-image"), (0, 0));
    }

    #[test]
    fn ocr文本解析兼容三种形态() {
        // 标准 content 数组形态
        let v1 = serde_json::json!({"output": {"choices": [{"message": {"content": [{"text": " 识别文本 "}]}}]}});
        assert_eq!(parse_ocr_text(&v1), Some("识别文本".to_string()));
        // 纯字符串 content 形态
        let v2 = serde_json::json!({"output": {"choices": [{"message": {"content": "直接文本"}}]}});
        assert_eq!(parse_ocr_text(&v2), Some("直接文本".to_string()));
        // 空响应
        let v3 = serde_json::json!({"output": {"choices": []}});
        assert_eq!(parse_ocr_text(&v3), None);
    }
}
