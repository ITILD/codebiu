//! 文件系统控制器(对齐 Python module_file/controller/filesystem.py)
//!
//! 全部端点挂载于 /file/filesystem 下; 权限码 main:file:{read,download,create,update,delete,migrate}。
//! 错误契约: 裸 {"detail": 文案}, 校验错误 422 detail 为 [{loc,msg,type}], 删除成功 204。

use axum::body::{Body, Bytes};
use axum::extract::{Multipart, Path, Query, State};
use axum::http::{header, StatusCode};
use axum::response::{IntoResponse, Response};
use axum::routing::{delete as del, get, post, put};
use axum::{Json, Router};
use serde::Deserialize;

use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::pagination::PaginationParams;

use module_authorization::deps::{authorize, AuthUserId, AuthUserIdOptional};

use crate::dao::file_entry_dao;
use crate::do_::filesystem::{
    check_len, check_range, BatchDeleteRequest, DownloadPermsRequest, EntryCreateRequest,
    FileEntryDetailResp, FileEntryResp, FileEntryUpdateReq, MigrateRequest, MultipartCompleteRequest,
    MultipartInitRequest,
};
use crate::services::filesystem::{can_download_entry, check_download_access, FileService};

/// 文件管理权限校验(main:file:{act})
async fn require_perm(user: &AuthUserId, act: &str) -> Result<(), AppError> {
    authorize(&user.0, "main", "file", act).await
}

/// 必填 query 参数(缺失 → 422, 与 FastAPI Field required 行为一致)
fn required_query(loc: &[&str], v: &Option<String>) -> Result<String, AppError> {
    v.clone().ok_or_else(|| AppError::validation(loc, "Field required"))
}

// ==================== query 参数载体 ====================

#[derive(Debug, Deserialize)]
struct UploadQuery {
    pid: Option<String>,
    description: Option<String>,
}

#[derive(Debug, Deserialize)]
struct PidQuery {
    pid: Option<String>,
}

#[derive(Debug, Deserialize)]
struct FolderQuery {
    name: Option<String>,
    pid: Option<String>,
}

#[derive(Debug, Deserialize)]
struct NewNameQuery {
    new_name: Option<String>,
}

#[derive(Debug, Deserialize)]
struct TargetPidQuery {
    target_pid: Option<String>,
}

#[derive(Debug, Deserialize)]
struct PathQuery {
    path: Option<String>,
}

#[derive(Debug, Deserialize)]
struct ListByPathQuery {
    path: Option<String>,
    name: Option<String>,
}

#[derive(Debug, Deserialize)]
struct KeywordQuery {
    keyword: Option<String>,
}

#[derive(Debug, Deserialize)]
struct CopyQuery {
    entry_id: Option<String>,
    target_pid: Option<String>,
}

pub fn router() -> Router<AppState> {
    Router::new()
        // 上传/浏览/目录
        .route("/upload", post(upload_file))
        .route("/list-dir", get(list_dir))
        .route("/dirs", get(list_dirs))
        .route("/folder", post(create_folder))
        // 条目更新/详情
        .route("/entries/{entry_id}", put(update_entry).get(get_file_entry_info))
        .route("/entries/{entry_id}/rename", put(rename_entry))
        .route("/entries/{entry_id}/move", put(move_entry))
        .route("/entries/{entry_id}/detail", get(get_file_entry_detail))
        .route("/entries/batch-delete", post(batch_delete_entries))
        // 上传模式/下载
        .route("/upload-mode", get(get_upload_mode))
        .route("/download/{entry_id}", get(download_file))
        .route("/download-perms", post(check_download_perms))
        // 分片上传
        .route("/multipart/init", post(init_multipart_upload))
        .route("/multipart/{upload_id}/parts/{part_number}", put(upload_multipart_part))
        .route("/multipart/{upload_id}/parts", get(list_multipart_parts))
        .route("/multipart/{upload_id}/complete", post(complete_multipart_upload))
        .route("/multipart/{upload_id}", del(abort_multipart_upload))
        // 秒传建条目
        .route("/upload-complete", post(create_entry))
        // 删除
        .route("/files/{file_id}", del(delete_file))
        .route("/folders/{folder_id}", del(delete_folder))
        // 路径操作/搜索/复制/统计/迁移
        .route("/path", get(get_entry_by_path))
        .route("/list-by-path", get(list_by_path))
        .route("/mkdir-p", post(mkdir_p))
        .route("/search", get(search_entries))
        .route("/copy", post(copy_entry))
        .route("/stats", get(get_stats))
        .route("/migrate", post(migrate_storage))
}

// ==================== 上传/浏览/目录 ====================

/// 上传文件到指定目录(小文件直传, 内容哈希去重) — 201
async fn upload_file(
    State(state): State<AppState>,
    user: AuthUserId,
    Query(q): Query<UploadQuery>,
    multipart: Multipart,
) -> Result<Response, AppError> {
    require_perm(&user, "create").await?;
    // 只取 file 字段; Python 口径 description/pid 为 query 参数(表单内其他字段忽略)
    let mut filename = String::new();
    let mut content: Option<Bytes> = None;
    let mut fields = multipart;
    while let Some(field) = fields
        .next_field()
        .await
        .map_err(|e| AppError::business(format!("文件解析失败: {e}")))?
    {
        if field.name() == Some("file") {
            if let Some(n) = field.file_name() {
                filename = n.to_string();
            }
            content = Some(
                field
                    .bytes()
                    .await
                    .map_err(|e| AppError::business(format!("文件读取失败: {e}")))?,
            );
            break;
        }
    }
    let Some(content) = content else {
        return Err(AppError::validation(&["body", "file"], "Field required"));
    };
    let service = FileService::new(state, true);
    let entry = service
        .upload_file(
            &filename,
            content,
            q.description.as_deref(),
            q.pid.as_deref(),
            Some(&user.0),
        )
        .await?;
    Ok((StatusCode::CREATED, Json(entry)).into_response())
}

/// 分页浏览指定目录下的子目录与文件(目录排前, 名称排序)
async fn list_dir(
    State(state): State<AppState>,
    user: AuthUserId,
    Query(p): Query<PaginationParams>,
    Query(q): Query<FolderQuery>,
) -> Result<Response, AppError> {
    require_perm(&user, "read").await?;
    p.validate()?;
    if let Some(name) = &q.name {
        check_len(&["query", "name"], name, 0, 255)?;
    }
    let service = FileService::new(state, false);
    let resp = service
        .list_by_pid(
            q.pid.as_deref().filter(|s| !s.is_empty()),
            &p,
            q.name.as_deref(),
        )
        .await?;
    Ok(Json(resp).into_response())
}

/// 查询指定目录下的全部子目录(目录树选择用)
async fn list_dirs(
    State(state): State<AppState>,
    user: AuthUserId,
    Query(q): Query<PidQuery>,
) -> Result<Response, AppError> {
    require_perm(&user, "read").await?;
    let service = FileService::new(state, false);
    let dirs = service
        .list_dirs(q.pid.as_deref().filter(|s| !s.is_empty()))
        .await?;
    Ok(Json(dirs).into_response())
}

/// 创建目录(虚拟文件系统) — 201
async fn create_folder(
    State(state): State<AppState>,
    user: AuthUserId,
    Query(q): Query<FolderQuery>,
) -> Result<Response, AppError> {
    require_perm(&user, "create").await?;
    let name = required_query(&["query", "name"], &q.name)?;
    check_len(&["query", "name"], &name, 1, 255)?;
    let service = FileService::new(state, true);
    let entry = service
        .create_folder(
            name,
            q.pid.as_deref().filter(|s| !s.is_empty()),
            Some(&user.0),
            None,
        )
        .await?;
    Ok((StatusCode::CREATED, Json(entry)).into_response())
}

// ==================== 条目更新/详情 ====================

/// 更新条目信息(名称变更自动维护路径)
async fn update_entry(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(entry_id): Path<String>,
    Json(req): Json<FileEntryUpdateReq>,
) -> Result<Response, AppError> {
    require_perm(&user, "update").await?;
    let service = FileService::new(state, true);
    let entry = service.update(&entry_id, req).await?;
    Ok(Json(entry).into_response())
}

/// 重命名条目(目录同步更新子树路径)
async fn rename_entry(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(entry_id): Path<String>,
    Query(q): Query<NewNameQuery>,
) -> Result<Response, AppError> {
    require_perm(&user, "update").await?;
    let new_name = required_query(&["query", "new_name"], &q.new_name)?;
    check_len(&["query", "new_name"], &new_name, 1, 255)?;
    let service = FileService::new(state, true);
    let entry = service.rename(&entry_id, &new_name).await?;
    Ok(Json(entry).into_response())
}

/// 移动条目到目标目录(目录同步更新子树路径)
async fn move_entry(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(entry_id): Path<String>,
    Query(q): Query<TargetPidQuery>,
) -> Result<Response, AppError> {
    require_perm(&user, "update").await?;
    let service = FileService::new(state, true);
    let entry = service.move_entry(&entry_id, q.target_pid).await?;
    Ok(Json(entry).into_response())
}

/// 获取条目详情(元数据/物理存储位置/上传用户名/标签等)
async fn get_file_entry_detail(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(entry_id): Path<String>,
) -> Result<Response, AppError> {
    require_perm(&user, "read").await?;
    let service = FileService::new(state, false);
    let detail: FileEntryDetailResp = service
        .get_entry_detail(&entry_id)
        .await?
        .ok_or_else(|| AppError::not_found("文件或目录不存在"))?;
    Ok(Json(detail).into_response())
}

/// 按ID获取文件或目录的基础元数据
async fn get_file_entry_info(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(entry_id): Path<String>,
) -> Result<Response, AppError> {
    require_perm(&user, "read").await?;
    let service = FileService::new(state, false);
    let entry: FileEntryResp = service
        .get_file_entry(&entry_id)
        .await?
        .map(FileEntryResp::from)
        .ok_or_else(|| AppError::not_found("文件或目录不存在"))?;
    Ok(Json(entry).into_response())
}

/// 批量删除条目(文件与目录混选, 目录递归删除子树)
async fn batch_delete_entries(
    State(state): State<AppState>,
    user: AuthUserId,
    Json(req): Json<BatchDeleteRequest>,
) -> Result<Response, AppError> {
    require_perm(&user, "delete").await?;
    let service = FileService::new(state, true);
    let result = service.batch_delete(req.entry_ids).await?;
    Ok(Json(result).into_response())
}

// ==================== 上传模式/下载 ====================

/// 查询上传模式(direct直传/proxy中转)
async fn get_upload_mode(
    State(state): State<AppState>,
    user: AuthUserId,
) -> Result<Response, AppError> {
    require_perm(&user, "read").await?;
    let service = FileService::new(state, false);
    let mode = service.get_upload_mode().await?;
    Ok(Json(mode).into_response())
}

/// 下载文件(s3直链302/local流式); avatar 来源允许匿名访问
async fn download_file(
    State(state): State<AppState>,
    Path(entry_id): Path<String>,
    user: AuthUserIdOptional,
) -> Result<Response, AppError> {
    // 下载鉴权: 404/401/403 口径与 Python get_download_user_id 一致
    check_download_access(&state, &entry_id, user.0.clone()).await?;
    let service = FileService::new(state.clone(), false);
    let (file_name, mime_type, file_key) = service.get_file_info_for_download(&entry_id).await?;
    // 直传存储: 预签名直链 302 重定向(浏览器直连, 服务端零流量)
    if let Some(url) = service.presign_download_url(&file_key, &file_name).await {
        return Ok((StatusCode::FOUND, [(header::LOCATION, url)]).into_response());
    }
    // 本地存储: 流式返回文件内容(分块读取, 支持大文件)
    let stream = service.stream_file_content(&file_key, 8192).await?;
    let mut builder = Response::builder()
        .header(header::CONTENT_DISPOSITION, format!("attachment; filename=\"{file_name}\""));
    if let Some(m) = mime_type {
        builder = builder.header(header::CONTENT_TYPE, m);
    }
    builder
        .body(Body::from_stream(stream))
        .map_err(|e| AppError::internal(format!("响应构建失败: {e}")))
}

/// 批量探测条目下载权限(前端下载按钮灰显用)
async fn check_download_perms(
    State(state): State<AppState>,
    user: AuthUserId,
    Json(req): Json<DownloadPermsRequest>,
) -> Result<Response, AppError> {
    require_perm(&user, "read").await?;
    let mut result = serde_json::Map::with_capacity(req.entry_ids.len());
    for entry_id in &req.entry_ids {
        // 判定口径与 /download 一致: 目录与不存在条目恒为 false
        let ok = match file_entry_dao::get(&state.db, entry_id).await? {
            Some(entry) if !entry.is_directory => {
                can_download_entry(&state, Some(&user.0), &entry).await
            }
            _ => false,
        };
        result.insert(entry_id.clone(), serde_json::Value::Bool(ok));
    }
    Ok(Json(serde_json::Value::Object(result)).into_response())
}

// ==================== 分片上传(multipart, 大文件) ====================

/// 初始化请求体校验(对齐 pydantic 字段约束, 违规 → 422)
fn validate_init_req(req: &MultipartInitRequest) -> Result<(), AppError> {
    check_len(&["body", "filename"], &req.filename, 1, 255)?;
    check_range(&["body", "file_size_bytes"], req.file_size_bytes, 1, i64::MAX)?;
    check_len(&["body", "content_hash"], &req.content_hash, 32, 64)?;
    if let Some(d) = &req.description {
        check_len(&["body", "description"], d, 0, 500)?;
    }
    Ok(())
}

/// 初始化分片上传会话(前端对 >10MB 文件自动分流调用)
async fn init_multipart_upload(
    State(state): State<AppState>,
    user: AuthUserId,
    Json(req): Json<MultipartInitRequest>,
) -> Result<Response, AppError> {
    require_perm(&user, "create").await?;
    validate_init_req(&req)?;
    let service = FileService::new(state, true);
    let resp = service.init_multipart_upload(&req).await?;
    Ok(Json(resp).into_response())
}

/// 上传单个分片(凭证即会话; 最后一片可小于标准分片大小)
async fn upload_multipart_part(
    State(state): State<AppState>,
    user: AuthUserId,
    Path((upload_id, part_number_raw)): Path<(String, String)>,
    body: Bytes,
) -> Result<Response, AppError> {
    require_perm(&user, "create").await?;
    // 分片号手工解析(FastAPI int 路径参数非法时为 422)
    let part_number: i64 = part_number_raw.parse().map_err(|_| {
        AppError::validation(
            &["path", "part_number"],
            "Input should be a valid integer, unable to parse string as an integer",
        )
    })?;
    if body.is_empty() {
        return Err(AppError::business("分片内容不能为空"));
    }
    let service = FileService::new(state, true);
    let info = service
        .upload_multipart_part(&upload_id, part_number, body)
        .await?;
    Ok(Json(info).into_response())
}

/// 查询已上传分片(断点续传)
async fn list_multipart_parts(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(upload_id): Path<String>,
) -> Result<Response, AppError> {
    require_perm(&user, "read").await?;
    let service = FileService::new(state, false);
    let parts = service.list_multipart_parts(&upload_id).await?;
    Ok(Json(parts).into_response())
}

/// 完成请求体校验(对齐 pydantic 字段约束)
fn validate_complete_req(req: &MultipartCompleteRequest) -> Result<(), AppError> {
    check_len(&["body", "filename"], &req.filename, 1, 255)?;
    if req.parts.is_empty() {
        return Err(AppError::validation(&["body", "parts"], "List should have at least 1 item"));
    }
    if let Some(d) = &req.description {
        check_len(&["body", "description"], d, 0, 500)?;
    }
    Ok(())
}

/// 完成分片上传(合并分片并创建条目) — 201
async fn complete_multipart_upload(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(upload_id): Path<String>,
    Json(req): Json<MultipartCompleteRequest>,
) -> Result<Response, AppError> {
    require_perm(&user, "create").await?;
    validate_complete_req(&req)?;
    let service = FileService::new(state, true);
    let entry = service
        .complete_multipart_upload(&upload_id, req, Some(&user.0))
        .await?;
    Ok((StatusCode::CREATED, Json(entry)).into_response())
}

/// 取消分片上传(清理已上传分片) — 204
async fn abort_multipart_upload(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(upload_id): Path<String>,
) -> Result<Response, AppError> {
    require_perm(&user, "delete").await?;
    let service = FileService::new(state, true);
    service.abort_multipart_upload(&upload_id).await?;
    Ok(StatusCode::NO_CONTENT.into_response())
}

// ==================== 秒传建条目/删除 ====================

/// 秒传建条目请求体校验(对齐 pydantic 字段约束)
fn validate_entry_req(req: &EntryCreateRequest) -> Result<(), AppError> {
    check_len(&["body", "name"], &req.name, 1, 255)?;
    check_len(&["body", "content_hash"], &req.content_hash, 32, 64)?;
    check_range(&["body", "file_size_bytes"], req.file_size_bytes, 1, i64::MAX)?;
    if let Some(m) = &req.mime_type {
        check_len(&["body", "mime_type"], m, 0, 100)?;
    }
    if let Some(d) = &req.description {
        check_len(&["body", "description"], d, 0, 500)?;
    }
    Ok(())
}

/// 秒传建条目(内容已存在时直接创建文件记录) — 201
async fn create_entry(
    State(state): State<AppState>,
    user: AuthUserId,
    Json(req): Json<EntryCreateRequest>,
) -> Result<Response, AppError> {
    require_perm(&user, "create").await?;
    validate_entry_req(&req)?;
    let service = FileService::new(state, true);
    let entry = service.create_entry(req, Some(&user.0)).await?;
    Ok((StatusCode::CREATED, Json(entry)).into_response())
}

/// 逻辑删除文件(释放内容引用, 归零清理物理文件) — 204
async fn delete_file(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(file_id): Path<String>,
) -> Result<Response, AppError> {
    require_perm(&user, "delete").await?;
    let service = FileService::new(state, true);
    service.delete_file(&file_id).await?;
    Ok(StatusCode::NO_CONTENT.into_response())
}

/// 递归逻辑删除目录(含全部子项) — 204
async fn delete_folder(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(folder_id): Path<String>,
) -> Result<Response, AppError> {
    require_perm(&user, "delete").await?;
    let service = FileService::new(state, true);
    service.delete_folder(&folder_id).await?;
    Ok(StatusCode::NO_CONTENT.into_response())
}

// ==================== 路径操作/搜索/复制/统计/迁移 ====================

/// 按逻辑路径查询条目(路径导航用)
async fn get_entry_by_path(
    State(state): State<AppState>,
    user: AuthUserId,
    Query(q): Query<PathQuery>,
) -> Result<Response, AppError> {
    require_perm(&user, "read").await?;
    let path = required_query(&["query", "path"], &q.path)?;
    check_len(&["query", "path"], &path, 1, 2000)?;
    let service = FileService::new(state, false);
    let entry = service
        .get_by_path(&path)
        .await?
        .ok_or_else(|| AppError::not_found(format!("路径不存在: {path}")))?;
    Ok(Json(entry).into_response())
}

/// 按逻辑路径浏览目录(目录排前, 名称排序)
async fn list_by_path(
    State(state): State<AppState>,
    user: AuthUserId,
    Query(p): Query<PaginationParams>,
    Query(q): Query<ListByPathQuery>,
) -> Result<Response, AppError> {
    require_perm(&user, "read").await?;
    p.validate()?;
    let path = required_query(&["query", "path"], &q.path)?;
    check_len(&["query", "path"], &path, 1, 2000)?;
    if let Some(name) = &q.name {
        check_len(&["query", "name"], name, 0, 255)?;
    }
    let service = FileService::new(state, false);
    let resp = service.list_by_path(&path, &p, q.name.as_deref()).await?;
    Ok(Json(resp).into_response())
}

/// 按逻辑路径递归创建目录(mkdir -p 语义, 已存在直接返回) — 201
async fn mkdir_p(
    State(state): State<AppState>,
    user: AuthUserId,
    Query(q): Query<PathQuery>,
) -> Result<Response, AppError> {
    require_perm(&user, "create").await?;
    let path = required_query(&["query", "path"], &q.path)?;
    check_len(&["query", "path"], &path, 1, 2000)?;
    let service = FileService::new(state, true);
    let entry = service.mkdir_p(&path, Some(&user.0)).await?;
    Ok((StatusCode::CREATED, Json(entry)).into_response())
}

/// 全树模糊搜索条目(匹配名称或逻辑路径)
async fn search_entries(
    State(state): State<AppState>,
    user: AuthUserId,
    Query(p): Query<PaginationParams>,
    Query(q): Query<KeywordQuery>,
) -> Result<Response, AppError> {
    require_perm(&user, "read").await?;
    p.validate()?;
    let keyword = required_query(&["query", "keyword"], &q.keyword)?;
    check_len(&["query", "keyword"], &keyword, 1, 255)?;
    let service = FileService::new(state, false);
    let resp = service.search(&keyword, &p).await?;
    Ok(Json(resp).into_response())
}

/// 复制条目(文件指向同一内容哈希, 目录递归整树复制) — 201
async fn copy_entry(
    State(state): State<AppState>,
    user: AuthUserId,
    Query(q): Query<CopyQuery>,
) -> Result<Response, AppError> {
    require_perm(&user, "create").await?;
    let entry_id = required_query(&["query", "entry_id"], &q.entry_id)?;
    let service = FileService::new(state, true);
    let entry = service
        .copy_entry(&entry_id, q.target_pid, Some(&user.0))
        .await?;
    Ok((StatusCode::CREATED, Json(entry)).into_response())
}

/// 存储统计(条目数/物理内容数/总占用/当前存储类型)
async fn get_stats(State(state): State<AppState>, user: AuthUserId) -> Result<Response, AppError> {
    require_perm(&user, "read").await?;
    let service = FileService::new(state, false);
    let stats = service.get_stats().await?;
    Ok(Json(stats).into_response())
}

/// 存储迁移(local<->s3 物理内容搬运, 切换配置前调用)
async fn migrate_storage(
    State(state): State<AppState>,
    user: AuthUserId,
    Json(req): Json<MigrateRequest>,
) -> Result<Response, AppError> {
    require_perm(&user, "migrate").await?;
    let service = FileService::new(state, true);
    let result = service.migrate_storage(req).await?;
    Ok(Json(result).into_response())
}
