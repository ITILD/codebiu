//! 文档解析控制器(对齐 Python controller/document_parse.py)
//!
//! 端点(挂载于 /office/document-parse 下, 仅要求登录无权限码, 对齐 get_current_user_id):
//! - POST /get-markdown-by-file  上传文件解析为 Markdown(响应为 JSON 字符串)
//! - POST /split-code            Python/Java 代码语义分块(仅 .py/.java)
//! 错误契约: 裸 {"detail": 文案}, 校验错误 422 detail 为 [{loc,msg,type}]。

use axum::body::Bytes;
use axum::extract::{Multipart, State};
use axum::routing::post;
use axum::{Json, Router};

use common::runtime::AppState;
use common::utils::error::AppError;
use module_authorization::deps::AuthUserId;

use crate::do_::chunk::Chunk;
use crate::services::document_parse as parse_service;
use crate::utils::file_parse::suffix_lower;

/// 子路由(nest 到 /document-parse 前缀)
pub fn router() -> Router<AppState> {
    Router::new()
        .route("/get-markdown-by-file", post(get_markdown_by_file))
        .route("/split-code", post(split_code_file))
}

/// 从 multipart 提取 file 字段(缺失 → 422, 对齐 FastAPI UploadFile 必填)
async fn take_file_field(multipart: Multipart) -> Result<(String, Bytes), AppError> {
    let mut fields = multipart;
    while let Some(field) = fields
        .next_field()
        .await
        .map_err(|e| AppError::business(format!("文件解析失败: {e}")))?
    {
        if field.name() == Some("file") {
            let filename = field.file_name().unwrap_or_default().to_string();
            let bytes = field
                .bytes()
                .await
                .map_err(|e| AppError::business(format!("文件读取失败: {e}")))?;
            return Ok((filename, bytes));
        }
    }
    Err(AppError::validation(&["body", "file"], "Field required"))
}

/// POST /get-markdown-by-file —— 上传文件解析为 Markdown
///
/// Python 侧返回 str(FastAPI 以 JSON 字符串编码), Rust 以 Json(String) 输出同构。
/// 说明: Python 的 DIR_TEMP 落盘为调试行为, Rust 不落盘直接内存解析。
async fn get_markdown_by_file(
    State(_state): State<AppState>,
    _user: AuthUserId,
    multipart: Multipart,
) -> Result<Json<String>, AppError> {
    let (filename, bytes) = take_file_field(multipart).await?;
    let markdown = parse_service::file2markdown(&filename, bytes).await?;
    Ok(Json(markdown))
}

/// POST /split-code —— 按语义结构拆分 Python/Java 代码文件
///
/// 仅支持 .py/.java(其余 400); 临时物理名对调用方无意义,
/// 分块 metadata.source 恢复为上传时的原始文件名(对齐 Python controller)。
async fn split_code_file(
    State(_state): State<AppState>,
    _user: AuthUserId,
    multipart: Multipart,
) -> Result<Json<Vec<Chunk>>, AppError> {
    let (filename, bytes) = take_file_field(multipart).await?;
    let suffix = suffix_lower(&filename);
    if suffix != ".py" && suffix != ".java" {
        return Err(AppError::business("仅支持 .py 和 .java 文件"));
    }
    let mut chunks = parse_service::file2chunk(&filename, bytes).await?;
    for chunk in &mut chunks {
        let metadata = chunk.metadata.get_or_insert_with(Default::default);
        metadata.insert("source".into(), serde_json::json!(filename));
    }
    Ok(Json(chunks))
}
