//! 项目文档业务服务(对齐 Python module_rag/service/project_document.py、
//! project_document_chunk.py), 含文档解析管线(Rust 降级口径)。
//!
//! 降级约定:
//! - 文本类文件(txt/md/csv/py/java)原生读取 + 简单滑动窗口分块;
//!   pdf/doc/docx/ppt/pptx 版式文档经 module-office 的 MinerU 引擎解析
//!   (远程 mineru.net API / 本地 docker 部署, 对齐 Python 默认引擎);
//!   xlsx 的 docling 引擎未实现 → 任务失败回写提示
//! - 向量化真实调用 module-ai embeddings, 但向量库引擎未实现 → 跳过向量写入,
//!   步骤置 skipped 并注明, 分块文本落 project_document_chunk 关系表

use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::pagination::PaginationParams;
use sea_orm::Set;

use crate::dao::document as doc_dao;
use crate::do_::document::{
    compute_ingest_progress, is_allowed_extension, is_text_extension, merge_ingest_steps,
    DocumentEntryItem, DocumentIngestProgress, ProjectDocumentResponse,
};
use crate::do_::entity::project_document;
use crate::do_::entity::project_document_chunk;
use crate::do_::user_model::model_type;
use crate::services::user_model as um_service;
use crate::services::project::ensure_project_folder;

/// 文档解析状态(对齐 Python ParseStatus StrEnum)
pub mod parse_status {
    pub const PENDING: &str = "pending";
    pub const PARSING: &str = "parsing";
    pub const COMPLETED: &str = "completed";
    pub const FAILED: &str = "failed";
}

/// 模型类型 → 中文名(缺失模型提示用, 对齐 Python _MODEL_TYPE_LABELS)
fn model_type_label(model_type: &str) -> &'static str {
    match model_type {
        model_type::CHAT => "对话(LLM)",
        model_type::EMBEDDINGS => "向量化(Embedding)",
        _ => "模型",
    }
}

/// 32 位 hex uuid
fn new_id() -> String {
    uuid::Uuid::new_v4().simple().to_string()
}

/// 上传前置校验: 项目存在 + 文件类型允许, 返回小写扩展名(不含点)
pub async fn validate_upload(state: &AppState, project_id: &str, filename: &str) -> Result<String, AppError> {
    if crate::dao::project::project_get(&state.db, project_id).await?.is_none() {
        tracing::error!("项目 {project_id} 不存在");
        return Err(AppError::not_found(format!("项目 {project_id} 不存在")));
    }
    if filename.is_empty() {
        return Err(AppError::business("文件名不能为空"));
    }
    let ext = filename.rsplit('.').next().unwrap_or("").to_lowercase();
    let ext = if filename.contains('.') { ext } else { String::new() };
    if !is_allowed_extension(&ext) {
        return Err(AppError::business(format!(
            "不支持的文件类型 '{ext}'，允许: {}",
            crate::do_::document::ALLOWED_EXTENSIONS.join("/")
        )));
    }
    Ok(ext)
}

/// 校验目录归属(目录不存在 404 / 不属于当前项目 400)
async fn validate_folder_in_project(
    state: &AppState,
    project_id: &str,
    folder_id: &str,
) -> Result<(), AppError> {
    let file_service = module_file::services::filesystem::FileService::new(state.clone(), true);
    let entry = file_service
        .get_file_entry(folder_id)
        .await?
        .filter(|e| e.is_directory && e.is_active)
        .ok_or_else(|| AppError::not_found(format!("目录不存在: {folder_id}")))?;
    // 目录必须位于项目根文件夹子树内(沿 pid 向上定位项目根)
    let root_id = ensure_project_folder(state, project_id, None).await?;
    let mut cursor = Some(entry);
    while let Some(e) = cursor {
        if e.id == root_id {
            return Ok(());
        }
        match e.pid {
            Some(pid) => cursor = file_service.get_file_entry(&pid).await?,
            None => break,
        }
    }
    Err(AppError::business("目标目录不属于当前项目"))
}

/// 上传文档并登记解析状态(文件经统一文件服务存储, project_document 记录知识库口径)
///
/// :param pid: 目标目录条目ID(空=项目根文件夹)
/// :return: (文档记录, 文件条目ID)
pub async fn upload_document(
    state: &AppState,
    project_id: &str,
    filename: &str,
    content: axum::body::Bytes,
    description: Option<String>,
    pid: Option<String>,
    owner_user_id: &str,
) -> Result<(ProjectDocumentResponse, String), AppError> {
    let ext = validate_upload(state, project_id, filename).await?;
    // 确保项目根文件夹并校验目标目录归属
    let root_id = ensure_project_folder(state, project_id, Some(owner_user_id)).await?;
    let target_pid = match pid {
        Some(p) => {
            validate_folder_in_project(state, project_id, &p).await?;
            p
        }
        None => root_id,
    };
    let file_service = module_file::services::filesystem::FileService::new(state.clone(), true);
    let entry = file_service
        .upload_file(
            filename,
            content,
            description.as_deref(),
            Some(&target_pid),
            Some(owner_user_id),
        )
        .await?;
    let doc_id = new_id();
    let model = doc_dao::document_add(
        &state.db,
        project_document::ActiveModel {
            id: Set(doc_id.clone()),
            project_id: Set(project_id.to_string()),
            name: Set(entry.name.clone()),
            file_extension: Set(ext),
            mime_type: Set(entry.mime_type.clone()),
            file_size_bytes: Set(entry.file_size_bytes.unwrap_or(0) as i32),
            physical_path: Set(String::new()),
            description: Set(description),
            parse_status: Set(parse_status::PENDING.to_string()),
            chunk_count: Set(0),
            error_message: Set(None),
            uploaded_by: Set(owner_user_id.to_string()),
            created_at: Set(Some(chrono::Utc::now().into())),
            updated_at: Set(chrono::Utc::now().into()),
            parse_steps: Set(serde_json::json!({})),
            content_hash: Set(entry.content_hash.clone()),
            entry_id: Set(Some(entry.id.clone())),
        },
    )
    .await?;
    Ok((ProjectDocumentResponse::from(model), entry.id))
}

/// 项目文档分页列表(可选名称/解析状态过滤)
pub async fn list_by_project(
    state: &AppState,
    project_id: &str,
    pagination: &PaginationParams,
    name: Option<String>,
    parse_status_filter: Option<String>,
) -> Result<common::utils::pagination::PaginationResponse<ProjectDocumentResponse>, AppError> {
    pagination.validate()?;
    let items = doc_dao::document_list_by_project(
        &state.db,
        project_id,
        name.as_deref(),
        parse_status_filter.as_deref(),
    )
    .await?;
    // 与 Python 一致: 过滤后的全量做内存分页(项目文档量级有限)
    let total = items.len() as i64;
    let start = pagination.offset() as usize;
    let page_items: Vec<ProjectDocumentResponse> = items
        .into_iter()
        .skip(start)
        .take(pagination.limit() as usize)
        .map(ProjectDocumentResponse::from)
        .collect();
    Ok(common::utils::pagination::PaginationResponse::create(page_items, total, pagination))
}

/// 项目文档条目浏览(目录排前 + 联查文档解析口径)
pub async fn list_entries(
    state: &AppState,
    project_id: &str,
    pid: Option<String>,
    name: Option<String>,
) -> Result<Vec<DocumentEntryItem>, AppError> {
    let root_id = ensure_project_folder(state, project_id, None).await?;
    let target_pid = match pid {
        Some(p) => {
            validate_folder_in_project(state, project_id, &p).await?;
            p
        }
        None => root_id,
    };
    let file_service = module_file::services::filesystem::FileService::new(state.clone(), false);
    let pagination = PaginationParams { page: 1, size: 500 };
    let items = file_service
        .list_by_pid(Some(&target_pid), &pagination, name.as_deref())
        .await?
        .items;
    // 联查文档口径: 条目ID → 文档记录
    let mut result = Vec::with_capacity(items.len());
    for entry in items {
        let doc = if entry.is_directory {
            None
        } else {
            doc_dao::document_list_by_project(&state.db, project_id, Some(&entry.name), None)
                .await?
                .into_iter()
                .find(|d| d.entry_id.as_deref() == Some(entry.id.as_str()))
        };
        result.push(DocumentEntryItem {
            id: entry.id,
            pid: entry.pid,
            name: entry.name,
            is_directory: entry.is_directory,
            file_size_bytes: entry.file_size_bytes,
            file_extension: entry.file_extension,
            mime_type: entry.mime_type,
            description: entry.description,
            created_at: entry.created_at,
            updated_at: entry.updated_at,
            document_id: doc.as_ref().map(|d| d.id.clone()),
            parse_status: doc.as_ref().map(|d| d.parse_status.clone()),
            chunk_count: doc.as_ref().map(|d| d.chunk_count),
            error_message: doc.as_ref().and_then(|d| d.error_message.clone()),
        });
    }
    // 目录排前, 各自按创建时间倒序(列表已按文件服务排序, 此处仅调目录优先)
    result.sort_by_key(|e| std::cmp::Reverse(e.is_directory));
    Ok(result)
}

/// 在项目下创建子目录(query name + pid; upload 档位)
pub async fn create_folder(
    state: &AppState,
    project_id: &str,
    name: &str,
    pid: Option<String>,
    owner: &str,
) -> Result<String, AppError> {
    let root_id = ensure_project_folder(state, project_id, Some(owner)).await?;
    let target_pid = match pid {
        Some(p) => {
            validate_folder_in_project(state, project_id, &p).await?;
            p
        }
        None => root_id,
    };
    let file_service = module_file::services::filesystem::FileService::new(state.clone(), true);
    let folder = file_service.create_folder(name.to_string(), Some(&target_pid), Some(owner), None).await?;
    Ok(folder.id)
}

/// 重命名项目内目录(update 档位; 项目根文件夹不允许改名)
pub async fn rename_folder(
    state: &AppState,
    project_id: &str,
    folder_id: &str,
    name: &str,
    _operator: &str,
) -> Result<(), AppError> {
    let root_id = ensure_project_folder(state, project_id, None).await?;
    if folder_id == root_id {
        return Err(AppError::business("项目根文件夹名称请通过修改项目名称变更"));
    }
    validate_folder_in_project(state, project_id, folder_id).await?;
    let file_service = module_file::services::filesystem::FileService::new(state.clone(), true);
    file_service.rename(folder_id, name).await?;
    Ok(())
}

/// 删除项目内目录(delete 档位; 项目根文件夹不允许删除)
pub async fn delete_folder(
    state: &AppState,
    project_id: &str,
    folder_id: &str,
    _operator: &str,
) -> Result<(), AppError> {
    let root_id = ensure_project_folder(state, project_id, None).await?;
    if folder_id == root_id {
        return Err(AppError::business("不能删除项目根文件夹"));
    }
    validate_folder_in_project(state, project_id, folder_id).await?;
    let file_service = module_file::services::filesystem::FileService::new(state.clone(), true);
    file_service.delete_folder(folder_id).await?;
    Ok(())
}

/// 按ID获取文档(404 文案对齐 Python controller: "文档不存在")
pub async fn get_document(state: &AppState, document_id: &str) -> Result<project_document::Model, AppError> {
    doc_dao::document_get(&state.db, document_id)
        .await?
        .ok_or_else(|| AppError::not_found("文档不存在"))
}

/// 文档入库步骤与进度响应
pub fn build_progress(document: &project_document::Model) -> DocumentIngestProgress {
    DocumentIngestProgress {
        document_id: document.id.clone(),
        parse_status: document.parse_status.clone(),
        progress: compute_ingest_progress(&document.parse_steps),
        steps: merge_ingest_steps(&document.parse_steps),
    }
}

/// 文档下载: 返回 (文件名, MIME类型, 物理存储键) 与条目口径标记
///
/// 条目级文档走统一文件服务; 内容级旧数据(content_hash)同样经服务读取物理键
pub async fn get_download_info(
    state: &AppState,
    document: &project_document::Model,
) -> Result<(String, Option<String>, String), AppError> {
    let file_service = module_file::services::filesystem::FileService::new(state.clone(), false);
    if let Some(entry_id) = &document.entry_id {
        return file_service.get_file_info_for_download(entry_id).await;
    }
    if let Some(hash) = &document.content_hash {
        let content = file_service
            .get_content(hash)
            .await?
            .ok_or_else(|| AppError::not_found(format!("物理内容记录不存在: {hash}")))?;
        let file_key = content
            .physical_storage
            .ok_or_else(|| AppError::not_found(format!("物理内容记录不存在: {hash}")))?;
        return Ok((document.name.clone(), document.mime_type.clone(), file_key));
    }
    Err(AppError::not_found(format!("物理文件 {} 不存在", document.physical_path)))
}

/// 更新文档元数据(name/description; 同步关联文件条目)
pub async fn update_document(
    state: &AppState,
    document_id: &str,
    req: crate::do_::document::ProjectDocumentUpdate,
) -> Result<(), AppError> {
    let document = get_document(state, document_id).await?;
    doc_dao::document_update(
        &state.db,
        document.clone(),
        req.name.clone(),
        req.description.clone().map(Some),
        None,
        None,
        None,
        None,
    )
    .await?;
    // 名称/描述变更同步文件条目(条目级口径)
    if let Some(entry_id) = &document.entry_id {
        let file_service = module_file::services::filesystem::FileService::new(state.clone(), true);
        let name = req.name.clone();
        let desc = req.description.clone();
        if name.is_some() || desc.is_some() {
            let _ = file_service
                .update(
                    entry_id,
                    module_file::do_::filesystem::FileEntryUpdateReq { name, description: desc, tags: None },
                )
                .await;
        }
    }
    Ok(())
}

/// 删除文档(物理内容引用释放 + 分块清理 + 记录删除)
pub async fn delete_document(state: &AppState, document_id: &str) -> Result<(), AppError> {
    let document = get_document(state, document_id).await?;
    let file_service = module_file::services::filesystem::FileService::new(state.clone(), true);
    if let Some(entry_id) = &document.entry_id {
        if let Err(e) = file_service.delete_file(entry_id).await {
            tracing::warn!("删除文档条目失败 {entry_id}: {e}");
        }
    } else if let Some(hash) = &document.content_hash {
        file_service.release_content_public(Some(hash)).await?;
    }
    doc_dao::chunk_delete_by_document(&state.db, document_id).await?;
    doc_dao::document_delete(&state.db, document_id).await?;
    Ok(())
}

/// 解析任务派发前模型预检(返回缺失模型中文名列表)
pub async fn ensure_parse_models(state: &AppState, user_id: &str) -> Result<Vec<String>, AppError> {
    let mut missing = Vec::new();
    for mt in [model_type::CHAT, model_type::EMBEDDINGS] {
        if um_service::resolve_model(state, user_id, mt).await?.model_id.is_none() {
            missing.push(model_type_label(mt).to_string());
        }
    }
    Ok(missing)
}

/// 派发文档解析任务("上传即解析"/手动解析共用), 返回 task_id
pub async fn dispatch_parse_task(
    state: &AppState,
    document: &project_document::Model,
    user_id: &str,
) -> Result<String, AppError> {
    let task_service = module_task::services::task::TaskQueueService::new(state.clone());
    task_service
        .create(
            module_task::do_::task::TaskQueueCreateReq {
                name: format!("解析文档: {}", document.name),
                task_type: "rag_document_parse".to_string(),
                payload: Some(serde_json::json!({ "document_id": document.id })),
                priority: 0,
            },
            user_id,
        )
        .await
}

// ==================== 解析管线(parse → chunk → embed) ====================

/// 更新指定步骤的 parse_steps 状态
async fn set_step(
    state: &AppState,
    document: &project_document::Model,
    step: &str,
    status: &str,
    progress: f64,
    message: Option<&str>,
    error: Option<&str>,
) -> Result<(), AppError> {
    let mut steps = document.parse_steps.clone();
    if !steps.is_object() {
        steps = serde_json::json!({});
    }
    steps[step] = serde_json::json!({
        "status": status,
        "progress": progress,
        "message": message,
        "error": error,
    });
    doc_dao::document_update(&state.db, document.clone(), None, None, None, None, None, Some(steps))
        .await?;
    Ok(())
}

/// 入库进度回调类型: (总进度0~100, 当前阶段描述)
pub type IngestProgressCb<'a> = &'a (dyn Fn(f64, String) -> std::pin::Pin<Box<dyn std::future::Future<Output = ()> + Send>> + Send + Sync);

/// 回报入库总进度(回调存在时 await 转发, 供任务层回写 task_queue.progress)
async fn report_progress(cb: Option<IngestProgressCb<'_>>, overall: f64, message: &str) {
    if let Some(cb) = cb {
        cb(overall, message.to_string()).await;
    }
}

/// 简单滑动窗口分块(块长 1024 字符 / 重叠 10%)
fn split_chunks(text: &str) -> Vec<String> {
    let max_chars = 1024usize;
    let overlap = max_chars / 10;
    let text = text.trim();
    if text.is_empty() {
        return Vec::new();
    }
    let mut chunks = Vec::new();
    let mut start = 0usize;
    while start < text.len() {
        let mut end = (start + max_chars).min(text.len());
        // 防止 UTF-8 字符被截断: 回退到字符边界
        while end < text.len() && !text.is_char_boundary(end) {
            end += 1;
        }
        chunks.push(text[start..end].to_string());
        if end >= text.len() {
            break;
        }
        start = end - overlap.min(end - start);
        while start < text.len() && !text.is_char_boundary(start) {
            start += 1;
        }
    }
    chunks
}

/// 落表分块口径(内容 + 类型/位置/元数据, 对齐 Python chunked_items 落表字段)
struct ParsedChunk {
    content: String,
    content_types: serde_json::Value,
    position: serde_json::Value,
    metadata: Option<serde_json::Value>,
}

/// 文档解析管线: 解析 → 分块 → 向量化(降级) → 分块落表, 内部维护 parse_status 与 parse_steps
///
/// 失败时文档置 failed + error_message(截断 1000), 错误上抛由任务层回写任务表
pub async fn parse_document(
    state: &AppState,
    document_id: &str,
    user_id: &str,
    progress_cb: Option<IngestProgressCb<'_>>,
) -> Result<(), AppError> {
    let document = get_document(state, document_id).await?;
    // 状态置 parsing + 步骤重置
    doc_dao::document_update(
        &state.db,
        document.clone(),
        None,
        None,
        Some(parse_status::PARSING.to_string()),
        Some(0),
        Some(None),
        Some(serde_json::json!({})),
    )
    .await?;

    // 按启用步骤权重计算总进度
    let weight = |step: &str| -> f64 {
        crate::do_::document::INGEST_PIPELINE
            .iter()
            .find(|s| s.step == step)
            .map(|s| s.weight)
            .unwrap_or(0.0)
    };
    let base_of = |finished: &[&str]| -> f64 {
        finished.iter().map(|s| weight(s)).sum::<f64>() / 100.0 * 100.0
    };

    let run = async {
        // ==================== 步骤1: 解析(文件 → 原始分块) ====================
        report_progress(progress_cb, base_of(&[]), "正在解析文档").await;
        set_step(state, &document, "parse", "running", 0.0, Some("正在解析文档"), None).await?;
        let file_service = module_file::services::filesystem::FileService::new(state.clone(), false);
        let entry_id = document.entry_id.clone().unwrap_or_else(|| document.id.clone());
        let parsed: Vec<ParsedChunk> = if is_text_extension(&document.file_extension) {
            // 文本类: 原生读取
            let text = file_service.read_file_text(&entry_id).await?;
            set_step(state, &document, "parse", "completed", 100.0, None, None).await?;
            // ==================== 步骤2: 分块(滑动窗口) ====================
            report_progress(progress_cb, base_of(&["parse"]), "正在拆分chunk").await;
            set_step(state, &document, "chunk", "running", 0.0, Some("正在拆分chunk"), None).await?;
            split_chunks(&text)
                .into_iter()
                .map(|content| ParsedChunk {
                    content,
                    content_types: serde_json::json!(["text"]),
                    position: serde_json::json!({}),
                    metadata: None,
                })
                .collect()
        } else {
            // 版式文档(pdf/doc/docx/ppt/pptx): module-office MinerU 引擎解析,
            // 解析即产出带 content_type/position/metadata 的分块(对齐 Python file2chunk)
            let bytes = file_service.read_file_bytes(&entry_id).await?;
            let chunks = module_office::services::document_parse::file2chunk(
                &document.name, bytes,
            )
            .await?;
            set_step(state, &document, "parse", "completed", 100.0, None, None).await?;
            report_progress(progress_cb, base_of(&["parse"]), "正在拆分chunk").await;
            set_step(state, &document, "chunk", "running", 0.0, Some("正在拆分chunk"), None).await?;
            chunks
                .into_iter()
                .filter_map(|c| {
                    let content = c.content?;
                    let ct = serde_json::to_value(c.content_type)
                        .unwrap_or_else(|_| serde_json::json!("text"));
                    Some(ParsedChunk {
                        content,
                        content_types: serde_json::json!([ct]),
                        position: serde_json::to_value(&c.position)
                            .unwrap_or_else(|_| serde_json::json!({})),
                        metadata: c.metadata.map(serde_json::Value::Object),
                    })
                })
                .collect()
        };
        if parsed.is_empty() {
            return Err(AppError::business("文档内容为空, 无法解析"));
        }
        set_step(state, &document, "chunk", "completed", 100.0, None, None).await?;

        // ==================== 步骤3: 向量化(真实调用, 跳过向量写入) ====================
        report_progress(progress_cb, base_of(&["parse", "chunk"]), "正在向量化").await;
        set_step(
            state,
            &document,
            "embed",
            "running",
            0.0,
            Some("正在向量化"),
            None,
        )
        .await?;
        let resolved = um_service::resolve_model(state, user_id, model_type::EMBEDDINGS).await?;
        let Some(embed_model_id) = resolved.model_id else {
            return Err(AppError::business(
                "无可用向量化模型, 请在设置中绑定或由管理员配置默认向量化模型",
            ));
        };
        let Some(target) = module_ai::services::llm::get_llm(&state.db, &embed_model_id, false).await?
        else {
            return Err(AppError::business(format!("加载向量化模型失败: {embed_model_id}")));
        };
        // 分批向量化(单批 16 条, 对齐常规 embedding 批量上限)
        let mut vectors = 0usize;
        for batch in parsed.chunks(16) {
            let batch_vec: Vec<String> = batch.iter().map(|c| c.content.clone()).collect();
            module_ai::utils::llm::embed(&state.http, &target, &batch_vec).await?;
            vectors += batch_vec.len();
            let p = if parsed.is_empty() {
                100.0
            } else {
                vectors as f64 / parsed.len() as f64 * 100.0
            };
            set_step(state, &document, "embed", "running", p, Some("正在向量化"), None).await?;
        }
        // 向量库引擎未实现: 步骤置 skipped, 分块文本落关系表
        set_step(
            state,
            &document,
            "embed",
            "skipped",
            100.0,
            Some("向量库引擎暂未在 Rust 服务实现， 已跳过向量写入"),
            None,
        )
        .await?;

        // ==================== 分块落表(替换式) ====================
        doc_dao::chunk_delete_by_document(&state.db, &document.id).await?;
        let mut rows = Vec::with_capacity(parsed.len());
        for (i, c) in parsed.iter().enumerate() {
            rows.push(project_document_chunk::ActiveModel {
                id: Set(new_id()),
                sort: Set(i as i32),
                document_id: Set(document.id.clone()),
                project_id: Set(document.project_id.clone()),
                content: Set(c.content.clone()),
                source: Set(document.name.clone()),
                content_types: Set(c.content_types.clone()),
                position: Set(c.position.clone()),
                metadata: Set(c.metadata.clone()),
            });
        }
        doc_dao::chunk_add_batch(&state.db, rows).await?;
        Ok(())
    };

    match run.await {
        Ok(()) => {
            // 成功: 文档置 completed + 实际分块数
            let count = doc_dao::chunk_list_by_document(&state.db, &document.id).await?.len() as i32;
            doc_dao::document_update(
                &state.db,
                document,
                None,
                None,
                Some(parse_status::COMPLETED.to_string()),
                Some(count),
                Some(None),
                None,
            )
            .await?;
            report_progress(progress_cb, 100.0, "解析完成").await;
            Ok(())
        }
        Err(e) => {
            // 失败: 文档置 failed + 错误信息(截断 1000)
            let msg = e.to_string();
            let short: String = msg.chars().take(1000).collect();
            let _ = doc_dao::document_update(
                &state.db,
                document,
                None,
                None,
                Some(parse_status::FAILED.to_string()),
                None,
                Some(Some(short)),
                None,
            )
            .await;
            Err(e)
        }
    }
}

// ==================== 分块服务(search/revectorize, 向量库降级口径) ====================

/// 按问题检索分块(向量库引擎未实现 → 400 降级提示, 对齐任务书口径)
pub async fn search_by_question(
    _state: &AppState,
    _user_id: &str,
    _req: crate::do_::document::SearchByQuestionRequest,
) -> Result<(), AppError> {
    Err(AppError::business("向量库引擎暂未在 Rust 服务实现"))
}

/// 全库重向量化任务执行体(向量库引擎未实现 → 任务失败)
pub async fn revectorize_all(_state: &AppState, _model_id: Option<String>) -> Result<(), String> {
    Err("向量库引擎暂未在 Rust 服务实现".to_string())
}
