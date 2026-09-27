//! OCR 控制器(对齐 Python controller/ocr.py; 前缀 /ocr, 全部端点 201)

use axum::extract::{Multipart, State};
use axum::http::StatusCode;
use axum::routing::{get, post};
use axum::{Json, Router};
use base64::Engine as _;
use base64::engine::general_purpose::STANDARD as BASE64;

use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::extract::AppJson;

use crate::do_::ocr::Base64File;
use crate::services::ocr as svc;

/// 从 multipart 中提取图片与 lang 表单字段
async fn parse_image_form(
    mut multipart: Multipart,
) -> Result<(Vec<u8>, String), AppError> {
    let mut image: Option<Vec<u8>> = None;
    let mut lang = String::new();
    while let Some(field) = multipart
        .next_field()
        .await
        .map_err(|e| AppError::validation(&["body", "form"], format!("表单解析失败: {e}")))?
    {
        match field.name().unwrap_or_default() {
            "image" => {
                let bytes = field
                    .bytes()
                    .await
                    .map_err(|e| AppError::validation(&["body", "image"], format!("图片读取失败: {e}")))?;
                image = Some(bytes.to_vec());
            }
            "lang" => lang = field.text().await.unwrap_or_default(),
            _ => {}
        }
    }
    let image = image
        .filter(|b| !b.is_empty())
        .ok_or_else(|| AppError::validation(&["body", "image"], "图片字段不能为空"))?;
    Ok((image, lang))
}

/// POST / —— 文字识别(启用检测与分类)
pub async fn recognize(
    State(state): State<AppState>,
    multipart: Multipart,
) -> Result<(StatusCode, Json<serde_json::Value>), AppError> {
    let (image, lang) = parse_image_form(multipart).await?;
    let result = svc::recognize(&state.db, &state.http, &image, &lang).await?;
    Ok((StatusCode::CREATED, Json(result)))
}

/// POST /segments —— 文字识别 -> 分栏分段
pub async fn segment_layout(
    State(state): State<AppState>,
    multipart: Multipart,
) -> Result<(StatusCode, Json<serde_json::Value>), AppError> {
    let (image, lang) = parse_image_form(multipart).await?;
    let result = svc::segment_layout(&state.db, &state.http, &image, &lang).await?;
    Ok((StatusCode::CREATED, Json(result)))
}

/// POST /layout —— 完整版面分析(本地版面分析模型未实现, 返回未实现错误)
pub async fn layout() -> Result<(StatusCode, Json<serde_json::Value>), AppError> {
    let result = svc::layout().await?;
    Ok((StatusCode::CREATED, Json(result)))
}

/// POST /all —— 文字识别 -> 分栏分段 + 版面分析(layout 恒为空数组)
pub async fn recognize_all(
    State(state): State<AppState>,
    multipart: Multipart,
) -> Result<(StatusCode, Json<serde_json::Value>), AppError> {
    let (image, lang) = parse_image_form(multipart).await?;
    let result = svc::recognize_all(&state.db, &state.http, &image, &lang, false).await?;
    Ok((StatusCode::CREATED, Json(result)))
}

/// GET /languages —— 返回可用语言列表(缺 ocr 配置返回空数组)
pub async fn get_languages() -> (StatusCode, Json<serde_json::Value>) {
    (StatusCode::OK, Json(svc::get_ocr_languages()))
}

/// POST /all-base64 —— 同 /all, 但图片以 base64 编码传入
pub async fn recognize_base64(
    State(state): State<AppState>,
    AppJson(req): AppJson<Base64File>,
) -> Result<(StatusCode, Json<serde_json::Value>), AppError> {
    let image = BASE64
        .decode(req.image_base64.trim())
        .map_err(|e| AppError::business(format!("图片 base64 解析失败: {e}")))?;
    let result = svc::recognize_all(&state.db, &state.http, &image, &req.lang, req.inpaint).await?;
    Ok((StatusCode::CREATED, Json(result)))
}

/// OCR 子路由(nest 到 /ocr 前缀)
pub fn router() -> Router<AppState> {
    Router::new()
        .route("/", post(recognize))
        .route("/segments", post(segment_layout))
        .route("/layout", post(layout))
        .route("/all", post(recognize_all))
        .route("/all-base64", post(recognize_base64))
        .route("/languages", get(get_languages))
}
