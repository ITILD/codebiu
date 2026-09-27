//! 项目文档/分块控制器(对齐 Python module_rag/controller/project_document.py、
//! project_document_chunk.py; 挂载前缀 /rag)

use axum::body::{Body, Bytes};
use axum::extract::{Multipart, Path, Query, State};
use axum::http::{header, StatusCode};
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post, put};
use axum::{Json, Router};
use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::pagination::{PaginationParams, PaginationResponse};
use percent_encoding::utf8_percent_encode;
use serde::Deserialize;
use serde_json::json;

use module_authorization::deps::AuthUserId;
use module_file::services::filesystem::FileService;

use crate::do_::document::{
    DocumentEntryItem, DocumentIngestProgress, ProjectDocumentResponse, SearchByQuestionRequest,
    RevectorizeAccepted, RevectorizeRequest, AUDIO_TYPES, DOCUMENT_TYPES, IMAGE_TYPES,
    VIDEO_TYPES, ALLOWED_EXTENSIONS,
};
use crate::services::document as svc;
use crate::services::permission::enforce_project_permission;

/// 项目级权限校验(对齐 Python require_project_permission: 成员档位判定)
async fn require_project_perm(
    state: &AppState,
    user_id: &str,
    project_id: &str,
    obj: &str,
    act: &str,
) -> Result<(), AppError> {
    enforce_project_permission(state, user_id, project_id, obj, act).await
}

/// 内存分页(DAO 返回全量后切片, 对齐 Python service 层分页语义)
fn paginate<T>(items: Vec<T>, pagination: &PaginationParams) -> PaginationResponse<T> {
    let total = items.len() as i64;
    let page = items
        .into_iter()
        .skip(pagination.offset() as usize)
        .take(pagination.limit() as usize)
        .collect();
    PaginationResponse::create(page, total, pagination)
}

// ==================== query 参数载体 ====================

#[derive(Debug, Deserialize)]
struct DocListQuery {
    #[serde(flatten)]
    pagination: PaginationParams,
    name: Option<String>,
    parse_status: Option<String>,
}

#[derive(Debug, Deserialize)]
struct EntryListQuery {
    #[serde(flatten)]
    pagination: PaginationParams,
    pid: Option<String>,
    name: Option<String>,
}

#[derive(Debug, Deserialize)]
struct FolderNameQuery {
    name: String,
    pid: Option<String>,
}

#[derive(Debug, Deserialize)]
struct RenameFolderQuery {
    name: String,
}

// ==================== 上传与列表 ====================

/// 上传成功后自动派发异步解析任务("上传即解析")
///
/// 模型缺失/派发失败时返回告警文案(parse_task_warning), 成功返回 None
async fn dispatch_parse_task(
    state: &AppState,
    document: &crate::do_::entity::project_document::Model,
    user_id: &str,
) -> Option<String> {
    match svc::ensure_parse_models(state, user_id).await {
        Ok(missing) if !missing.is_empty() => Some(format!(
            "文档已上传, 但解析任务未派发: 未配置可用的{}模型, 请先在模型管理中绑定或由管理员配置默认公共模型",
            missing.join("、")
        )),
        Ok(_) => match svc::dispatch_parse_task(state, document, user_id).await {
            Ok(_) => None,
            Err(e) => {
                tracing::warn!("自动派发解析任务失败(可手动解析) document_id={}: {e}", document.id);
                Some(format!("文档已上传, 但解析任务派发失败(可手动重试): {e}"))
            }
        },
        Err(e) => {
            tracing::warn!("解析模型预检失败 document_id={}: {e}", document.id);
            Some(format!("文档已上传, 但解析任务未派发: {e}"))
        }
    }
}

/// 上传文档到项目(小文件直传口径; 201 返回文档元数据)
async fn upload_project_document(
    State(state): State<AppState>,
    Path(project_id): Path<String>,
    user: AuthUserId,
    mut multipart: Multipart,
) -> Result<(StatusCode, Json<ProjectDocumentResponse>), AppError> {
    require_project_perm(&state, &user.0, &project_id, "doc", "upload").await?;
    // 表单字段: file(必填) + description/pid(可选, 对齐 Python Form 字段)
    let mut filename = String::new();
    let mut content: Option<Bytes> = None;
    let mut description: Option<String> = None;
    let mut pid: Option<String> = None;
    while let Some(field) = multipart
        .next_field()
        .await
        .map_err(|e| AppError::business(format!("文件解析失败: {e}")))?
    {
        match field.name() {
            Some("file") => {
                if let Some(n) = field.file_name() {
                    filename = n.to_string();
                }
                content = Some(field.bytes().await.map_err(|e| {
                    AppError::business(format!("读取上传文件失败: {e}"))
                })?);
            }
            Some("description") => {
                description = Some(field.text().await.unwrap_or_default()).filter(|s| !s.is_empty());
            }
            Some("pid") => {
                pid = Some(field.text().await.unwrap_or_default()).filter(|s| !s.is_empty());
            }
            _ => {}
        }
    }
    let content = content.filter(|c| !c.is_empty()).ok_or_else(|| {
        AppError::validation(&["body", "file"], "Field required")
    })?;
    let (document, _entry_id) =
        svc::upload_document(&state, &project_id, &filename, content, description, pid, &user.0)
            .await?;
    // 上传成功后自动派发异步解析任务(模型缺失/队列不可用时返回告警)
    let mut response = document;
    let raw = svc::get_document(&state, &response.id).await?;
    response.parse_task_warning = dispatch_parse_task(&state, &raw, &user.0).await;
    Ok((StatusCode::CREATED, Json(response)))
}

/// 分页查询项目文档列表(支持名称/解析状态过滤)
async fn list_project_documents(
    State(state): State<AppState>,
    Path(project_id): Path<String>,
    user: AuthUserId,
    Query(q): Query<DocListQuery>,
) -> Result<Json<PaginationResponse<ProjectDocumentResponse>>, AppError> {
    require_project_perm(&state, &user.0, &project_id, "doc", "read").await?;
    if let Some(s) = q.parse_status.as_deref() {
        if !crate::do_::document::is_valid_parse_status(s) {
            return Err(AppError::business(format!("无效的解析状态 '{s}'，允许: pending/parsing/completed/failed")));
        }
    }
    Ok(Json(
        svc::list_by_project(&state, &project_id, &q.pagination, q.name, q.parse_status).await?,
    ))
}

/// 获取支持上传的文件格式列表(无鉴权, 信封响应对齐 Python)
async fn get_supported_file_types() -> Json<serde_json::Value> {
    Json(json!({
        "code": 200,
        "message": "success",
        "data": {
            "documents": DOCUMENT_TYPES,
            "images": IMAGE_TYPES,
            "audios": AUDIO_TYPES,
            "videos": VIDEO_TYPES,
            "all_extensions": ALLOWED_EXTENSIONS,
        }
    }))
}

/// 查询知识库文档上传模式(direct 预签名直传 / proxy 服务端中转)
async fn get_rag_upload_mode(
    State(state): State<AppState>,
    _user: AuthUserId,
) -> Result<Json<module_file::do_::filesystem::UploadModeResponse>, AppError> {
    let file_service = FileService::new(state.clone(), false);
    Ok(Json(file_service.get_upload_mode().await?))
}

/// 校验当前用户解析文档所需模型是否可用(前端提交解析前弹窗警告)
async fn check_rag_parse_models(
    State(state): State<AppState>,
    user: AuthUserId,
) -> Result<Json<serde_json::Value>, AppError> {
    let missing = svc::ensure_parse_models(&state, &user.0).await?;
    let message = if missing.is_empty() {
        None
    } else {
        Some(format!(
            "未配置可用的{}模型, 无法解析文档; 请先在模型管理中绑定或由管理员配置默认公共模型",
            missing.join("、")
        ))
    };
    Ok(Json(json!({ "ok": missing.is_empty(), "missing": missing, "message": message })))
}

// ==================== 项目内目录与条目浏览 ====================

/// 浏览项目内文件夹与文件(目录排前; 内存分页)
async fn list_project_entries(
    State(state): State<AppState>,
    Path(project_id): Path<String>,
    user: AuthUserId,
    Query(q): Query<EntryListQuery>,
) -> Result<Json<PaginationResponse<DocumentEntryItem>>, AppError> {
    require_project_perm(&state, &user.0, &project_id, "doc", "read").await?;
    let items = svc::list_entries(&state, &project_id, q.pid, q.name).await?;
    Ok(Json(paginate(items, &q.pagination)))
}

/// 在项目内创建文件夹(201 返回条目)
async fn create_project_folder(
    State(state): State<AppState>,
    Path(project_id): Path<String>,
    user: AuthUserId,
    Query(q): Query<FolderNameQuery>,
) -> Result<(StatusCode, Json<module_file::do_::filesystem::FileEntryResp>), AppError> {
    require_project_perm(&state, &user.0, &project_id, "doc", "upload").await?;
    if q.name.trim().is_empty() {
        return Err(AppError::validation(&["query", "name"], "String should have at least 1 character"));
    }
    let folder_id = svc::create_folder(&state, &project_id, &q.name, q.pid, &user.0).await?;
    let file_service = FileService::new(state.clone(), false);
    let entry = file_service
        .get_file_entry(&folder_id)
        .await?
        .ok_or_else(|| AppError::not_found(format!("未找到ID为 {folder_id} 的文件")))?;
    Ok((StatusCode::CREATED, Json(entry.into())))
}

/// 重命名项目内文件夹(返回更新后的条目)
async fn rename_project_folder(
    State(state): State<AppState>,
    Path((project_id, folder_id)): Path<(String, String)>,
    user: AuthUserId,
    Query(q): Query<RenameFolderQuery>,
) -> Result<Json<module_file::do_::filesystem::FileEntryResp>, AppError> {
    require_project_perm(&state, &user.0, &project_id, "doc", "update").await?;
    if q.name.trim().is_empty() {
        return Err(AppError::validation(&["query", "name"], "String should have at least 1 character"));
    }
    svc::rename_folder(&state, &project_id, &folder_id, &q.name, &user.0).await?;
    let file_service = FileService::new(state.clone(), false);
    let entry = file_service
        .get_file_entry(&folder_id)
        .await?
        .ok_or_else(|| AppError::not_found(format!("未找到ID为 {folder_id} 的文件")))?;
    Ok(Json(entry.into()))
}

/// 删除项目内文件夹(递归删除条目并释放内容引用; 204)
async fn delete_project_folder(
    State(state): State<AppState>,
    Path((project_id, folder_id)): Path<(String, String)>,
    user: AuthUserId,
) -> Result<StatusCode, AppError> {
    require_project_perm(&state, &user.0, &project_id, "doc", "delete").await?;
    svc::delete_folder(&state, &project_id, &folder_id, &user.0).await?;
    Ok(StatusCode::NO_CONTENT)
}

// ==================== 文档详情/进度/下载/编辑/删除/解析 ====================

/// 获取文档详情(项目级 read 档位)
async fn get_project_document(
    State(state): State<AppState>,
    Path(document_id): Path<String>,
    user: AuthUserId,
) -> Result<Json<ProjectDocumentResponse>, AppError> {
    let document = svc::get_document(&state, &document_id).await?;
    enforce_project_permission(&state, &user.0, &document.project_id, "doc", "read").await?;
    Ok(Json(ProjectDocumentResponse::from(document)))
}

/// 查询文档入库步骤与进度(前端轮询渲染步骤条)
async fn get_project_document_progress(
    State(state): State<AppState>,
    Path(document_id): Path<String>,
    user: AuthUserId,
) -> Result<Json<DocumentIngestProgress>, AppError> {
    let document = svc::get_document(&state, &document_id).await?;
    enforce_project_permission(&state, &user.0, &document.project_id, "doc", "read").await?;
    Ok(Json(svc::build_progress(&document)))
}

/// 下载文档(S3 预签名直链 302 / 本地流式)
async fn download_project_document(
    State(state): State<AppState>,
    Path(document_id): Path<String>,
    user: AuthUserId,
) -> Result<Response, AppError> {
    let document = svc::get_document(&state, &document_id).await?;
    // 下载独立于 read, 需 editor 及以上档位
    enforce_project_permission(&state, &user.0, &document.project_id, "doc", "download").await?;
    let (file_name, mime_type, source) = svc::get_download_info(&state, &document).await?;
    // Content-Disposition: ASCII 回退 + RFC 5987 filename*(支持中文等非 ASCII 文件名)
    let ascii_fallback: String = file_name.chars().filter(|c| c.is_ascii()).collect();
    let ascii_fallback = if ascii_fallback.is_empty() { "download".to_string() } else { ascii_fallback };
    let encoded_name = utf8_percent_encode(&file_name, &PYTHON_QUOTE_SAFE).to_string();
    let disposition = format!(
        "attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded_name}"
    );
    let file_service = FileService::new(state.clone(), false);
    // 统一存储口径: S3 签发预签名直链 302 重定向(服务端零流量); 否则流式代理
    if let Some(url) = file_service.presign_download_url(&source, &file_name).await {
        let mut redirect = StatusCode::FOUND.into_response();
        redirect
            .headers_mut()
            .insert(header::LOCATION, url.parse().expect("预签名 URL 解析"));
        return Ok(redirect);
    }
    let stream = file_service.stream_file_content(&source, 64 * 1024).await?;
    let mut response = Body::from_stream(stream).into_response();
    let headers = response.headers_mut();
    headers.insert(header::CONTENT_DISPOSITION, disposition.parse().expect("静态头解析"));
    headers.insert(
        header::CONTENT_TYPE,
        mime_type
            .unwrap_or_else(|| "application/octet-stream".to_string())
            .parse()
            .unwrap_or_else(|_| "application/octet-stream".parse().expect("静态头解析")),
    );
    Ok(response)
}

/// Python urllib.parse.quote 默认 safe='/' 的编码集(字母数字与 -._~ 不编码)
const PYTHON_QUOTE_SAFE: &percent_encoding::AsciiSet = &percent_encoding::CONTROLS
    .add(b' ')
    .add(b'"')
    .add(b'#')
    .add(b'%')
    .add(b'&')
    .add(b'\'')
    .add(b'+')
    .add(b',')
    .add(b':')
    .add(b';')
    .add(b'<')
    .add(b'>')
    .add(b'=')
    .add(b'?')
    .add(b'@')
    .add(b'[')
    .add(b'\\')
    .add(b']')
    .add(b'^')
    .add(b'`')
    .add(b'{')
    .add(b'|')
    .add(b'}');

/// 更新文档元数据(204; 仅 name/description)
async fn update_project_document(
    State(state): State<AppState>,
    Path(document_id): Path<String>,
    user: AuthUserId,
    Json(req): Json<crate::do_::document::ProjectDocumentUpdate>,
) -> Result<StatusCode, AppError> {
    let document = svc::get_document(&state, &document_id).await?;
    enforce_project_permission(&state, &user.0, &document.project_id, "doc", "update").await?;
    svc::update_document(&state, &document_id, req).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// 删除文档(释放物理内容与数据库记录; 204)
async fn delete_project_document(
    State(state): State<AppState>,
    Path(document_id): Path<String>,
    user: AuthUserId,
) -> Result<StatusCode, AppError> {
    let document = svc::get_document(&state, &document_id).await?;
    enforce_project_permission(&state, &user.0, &document.project_id, "doc", "delete").await?;
    svc::delete_document(&state, &document_id).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// 重新解析文档(同步直跑版, 仅调试用: 阻塞至解析完成)
async fn reparse_project_document(
    State(state): State<AppState>,
    Path(document_id): Path<String>,
    user: AuthUserId,
) -> Result<Json<bool>, AppError> {
    let document = svc::get_document(&state, &document_id).await?;
    enforce_project_permission(&state, &user.0, &document.project_id, "doc", "update").await?;
    svc::parse_document(&state, &document_id, &user.0, None).await?;
    Ok(Json(true))
}

/// 重新解析文档加入任务队列(模型缺失时 400 供前端弹窗)
async fn reparse_project_document_task(
    State(state): State<AppState>,
    Path(document_id): Path<String>,
    user: AuthUserId,
) -> Result<Json<serde_json::Value>, AppError> {
    let document = svc::get_document(&state, &document_id).await?;
    enforce_project_permission(&state, &user.0, &document.project_id, "doc", "update").await?;
    // 模型预检: 对话+向量化模型缺失时拒绝入队(前端弹窗提示)
    let missing = svc::ensure_parse_models(&state, &user.0).await?;
    if !missing.is_empty() {
        return Err(AppError::business(format!(
            "未配置可用的{}模型, 无法解析文档; 请先在模型管理中绑定或由管理员配置默认公共模型",
            missing.join("、")
        )));
    }
    let task_id = svc::dispatch_parse_task(&state, &document, &user.0).await?;
    Ok(Json(json!({
        "message": "解析任务已提交至后台队列",
        "document_id": document_id,
        "task_id": task_id,
    })))
}

// ==================== 分块检索与全库重向量化(/rag/project-document-chunks) ====================

/// 按问题检索项目相似文档块(向量库引擎未实现 → 400 降级提示)
async fn chunks_by_question(
    State(_state): State<AppState>,
    _user: AuthUserId,
    Json(_req): Json<SearchByQuestionRequest>,
) -> Result<Json<serde_json::Value>, AppError> {
    Err(AppError::business("向量库引擎暂未在 Rust 服务实现"))
}

/// task_queue 库中状态 → Celery 状态(status 接口响应格式兼容)
fn db_state_to_celery(status: &str) -> &'static str {
    match status {
        "pending" => "PENDING",
        "running" => "PROGRESS",
        "success" => "SUCCESS",
        "failed" => "FAILURE",
        "cancelled" | "revoked" => "REVOKED",
        _ => "PENDING",
    }
}

/// 全库重向量化(202 受理; 仅系统管理员)
async fn revectorize_chunks(
    State(state): State<AppState>,
    user: AuthUserId,
    Json(req): Json<RevectorizeRequest>,
) -> Result<(StatusCode, Json<RevectorizeAccepted>), AppError> {
    if !module_authorization::casbin_mgr::auth().is_global_admin(&user.0).await {
        return Err(AppError::forbidden("仅系统管理员可执行全库重向量化"));
    }
    let task_service = module_task::services::task::TaskQueueService::new(state.clone());
    let task_id = task_service
        .create(
            module_task::do_::task::TaskQueueCreateReq {
                name: "全库重向量化".to_string(),
                task_type: "rag_revectorize".to_string(),
                payload: Some(json!({ "model_id": req.model_id })),
                priority: 0,
            },
            &user.0,
        )
        .await?;
    Ok((
        StatusCode::ACCEPTED,
        Json(RevectorizeAccepted { task_id, message: "重向量化任务已提交".to_string() }),
    ))
}

/// 查询全库重向量化任务进度(仅系统管理员)
async fn revectorize_status(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(task_id): Path<String>,
) -> Result<Json<serde_json::Value>, AppError> {
    if !module_authorization::casbin_mgr::auth().is_global_admin(&user.0).await {
        return Err(AppError::forbidden("仅系统管理员可查询重向量化进度"));
    }
    let task = module_task::dao::task_dao::get(&state.db, &task_id)
        .await?
        .ok_or_else(|| AppError::not_found(format!("任务 {task_id} 不存在")))?;
    let state_str = db_state_to_celery(&task.status);
    let mut response = json!({ "task_id": task_id, "state": state_str });
    if state_str == "PROGRESS" {
        response["meta"] = json!({
            "progress": task.progress,
            "message": task.message,
        });
    } else if state_str == "FAILURE" {
        response["error"] = json!(task.error.unwrap_or_else(|| "任务执行失败".to_string()));
    }
    Ok(Json(response))
}

pub(crate) fn documents_router() -> Router<AppState> {
    Router::new()
        .route("/{project_id}/upload", post(upload_project_document))
        .route("/{project_id}/list", get(list_project_documents))
        .route("/supported-types", get(get_supported_file_types))
        .route("/upload-mode", get(get_rag_upload_mode))
        .route("/model-check", get(check_rag_parse_models))
        .route("/{project_id}/entries", get(list_project_entries))
        .route("/{project_id}/folders", post(create_project_folder))
        .route(
            "/{project_id}/folders/{folder_id}",
            put(rename_project_folder).delete(delete_project_folder),
        )
        .route(
            "/{document_id}",
            get(get_project_document).put(update_project_document).delete(delete_project_document),
        )
        .route("/{document_id}/progress", get(get_project_document_progress))
        .route("/{document_id}/download", get(download_project_document))
        .route("/{document_id}/reparse", post(reparse_project_document))
        .route("/{document_id}/reparse-task", post(reparse_project_document_task))
}

pub(crate) fn chunks_router() -> Router<AppState> {
    Router::new()
        .route("/search-by-question", post(chunks_by_question))
        .route("/revectorize", post(revectorize_chunks))
        .route("/revectorize/status/{task_id}", get(revectorize_status))
}
