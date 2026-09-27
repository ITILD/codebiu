//! 用户头像控制器(对齐 Python module_authorization/controller/auth.py 的 /me/avatar 两端点)
//!
//! 契约路径: /authorization/auth/me/avatar(由 app 挂载到 /authorization 前缀下, 前端零改动);
//! 登录即可调用(无需权限码), 文件字段缺失 → 422, 删除成功 → 204。

use axum::body::Bytes;
use axum::extract::{Multipart, State};
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::routing::post;
use axum::{Json, Router};

use common::runtime::AppState;
use common::utils::error::AppError;

use module_authorization::deps::AuthUser;

use crate::services::avatar::AvatarService;

/// 头像路由(对应 Python auth router 的 /me/avatar, 子前缀 /auth 由本路由携带)
pub fn router() -> Router<AppState> {
    Router::new().route("/auth/me/avatar", post(upload_avatar).delete(delete_avatar))
}

/// 上传当前用户头像(登录即可) — 200 {"avatar": 下载路径, "entry_id": 条目ID}
///
/// Python: file: UploadFile = File(...), 字段名固定 "file", 缺失由 FastAPI 422
async fn upload_avatar(
    State(state): State<AppState>,
    user: AuthUser,
    multipart: Multipart,
) -> Result<Response, AppError> {
    // 只取 file 字段(其余表单字段忽略, 与 Python 单参数签名一致)
    let mut filename = String::new();
    let mut content: Option<Bytes> = None;
    let mut fields = multipart;
    while let Some(field) = fields
        .next_field()
        .await
        .map_err(|e| AppError::business(format!("文件解析失败: {e}")))?
    {
        if field.name() == Some("file") {
            filename = field.file_name().unwrap_or_default().to_string();
            content = Some(
                field
                    .bytes()
                    .await
                    .map_err(|e| AppError::business(format!("文件读取失败: {e}")))?,
            );
            break;
        }
    }
    let content = content.ok_or_else(|| AppError::validation(&["body", "file"], "Field required"))?;
    let service = AvatarService::new(state);
    let resp = service.upload_avatar(user.id(), &filename, content).await?;
    Ok(Json(resp).into_response())
}

/// 删除当前用户头像还原默认首字头像(登录即可) — 204
async fn delete_avatar(
    State(state): State<AppState>,
    user: AuthUser,
) -> Result<StatusCode, AppError> {
    AvatarService::new(state).delete_avatar(user.id()).await?;
    Ok(StatusCode::NO_CONTENT)
}
