//! OCR DTO(对齐 Python module_ai/do/ocr.py)

use serde::Deserialize;

/// base64 图片识别请求体(POST /ai/ocr/all-base64)
#[derive(Debug, Clone, Deserialize)]
pub struct Base64File {
    pub image_base64: String,
    pub lang: String,
    #[serde(default)]
    pub inpaint: bool,
}
