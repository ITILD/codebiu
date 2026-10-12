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

/// Json 值转字符串列表(向量库 Array<VarChar> 写入口径; 非数组/元素非字符串时返回空)
fn json_str_list(v: &serde_json::Value) -> Vec<String> {
    v.as_array()
        .map(|arr| {
            arr.iter()
                .filter_map(|i| i.as_str().map(String::from))
                .collect()
        })
        .unwrap_or_default()
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
    let file_service = module_file::services::filesystem::FileService::new(state.clone(), false);
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
    let file_service = module_file::services::filesystem::FileService::new(state.clone(), false);
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
    let file_service = module_file::services::filesystem::FileService::new(state.clone(), false);
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
    let file_service = module_file::services::filesystem::FileService::new(state.clone(), false);
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
    let file_service = module_file::services::filesystem::FileService::new(state.clone(), false);
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
        let file_service = module_file::services::filesystem::FileService::new(state.clone(), false);
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
    let file_service = module_file::services::filesystem::FileService::new(state.clone(), false);
    if let Some(entry_id) = &document.entry_id {
        if let Err(e) = file_service.delete_file(entry_id).await {
            tracing::warn!("删除文档条目失败 {entry_id}: {e}");
        }
    } else if let Some(hash) = &document.content_hash {
        file_service.release_content_public(Some(hash)).await?;
    }
    // 向量库分块同步清理(未启用向量库时跳过; 失败仅告警不阻断删除)
    if let Some(client) = common::utils::db_vector::get(state).await {
        if let Err(e) = client.delete_by_document(document_id).await {
            tracing::warn!("清理文档向量失败 {document_id}: {e}");
        }
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
            // 去除 UTF-8 BOM 前缀(Windows 编辑器常见, 避免污染首个分块的分词)
            let text = text.strip_prefix('\u{feff}').map(String::from).unwrap_or(text);
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

        // ==================== 步骤3: 向量化(真实调用 + 写入 Milvus) ====================
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
        // 预生成分块ID(关系表与向量库同 id, 两边数据可互查)
        let chunk_ids: Vec<String> = (0..parsed.len()).map(|_| new_id()).collect();
        // 分批向量化(单批 16 条, 对齐常规 embedding 批量上限), 收集向量待写入
        let mut all_vectors: Vec<Vec<f64>> = Vec::with_capacity(parsed.len());
        for batch in parsed.chunks(16) {
            let batch_vec: Vec<String> = batch.iter().map(|c| c.content.clone()).collect();
            let vectors = module_ai::utils::llm::embed(&state.http, &target, &batch_vec).await?;
            all_vectors.extend(vectors);
            let p = if parsed.is_empty() {
                100.0
            } else {
                all_vectors.len() as f64 / parsed.len() as f64 * 100.0
            };
            set_step(state, &document, "embed", "running", p, Some("正在向量化"), None).await?;
        }
        // 写入 Milvus 向量库(未启用向量库时步骤置 skipped 降级, 分块文本仍落关系表)
        match common::utils::db_vector::get(state).await {
            Some(client) => {
                let rows: Vec<common::utils::db_vector::ChunkRow> = parsed
                    .iter()
                    .zip(chunk_ids.iter())
                    .zip(all_vectors.iter())
                    .map(|((c, id), vec)| common::utils::db_vector::ChunkRow {
                        id: id.clone(),
                        sort: 0,
                        document_id: document.id.clone(),
                        project_id: document.project_id.clone(),
                        content: c.content.clone(),
                        source: document.name.clone(),
                        content_types: json_str_list(&c.content_types),
                        position: c.position.clone(),
                        metadata: c.metadata.clone().unwrap_or(serde_json::json!({})),
                        embedding: vec.clone(),
                    })
                    .collect();
                // 替换式写入: 先清旧向量再插入(与关系表 chunk_delete_by_document 同语义)
                let _ = client.delete_by_document(&document.id).await;
                client.insert_chunks(rows).await.map_err(AppError::business)?;
                set_step(state, &document, "embed", "completed", 100.0, None, None).await?;
            }
            None => {
                set_step(
                    state,
                    &document,
                    "embed",
                    "skipped",
                    100.0,
                    Some("向量库未启用，已跳过向量写入"),
                    None,
                )
                .await?;
            }
        }

        // ==================== 分块落表(替换式) ====================
        doc_dao::chunk_delete_by_document(&state.db, &document.id).await?;
        let mut rows = Vec::with_capacity(parsed.len());
        for (i, (c, id)) in parsed.iter().zip(chunk_ids.iter()).enumerate() {
            rows.push(project_document_chunk::ActiveModel {
                id: Set(id.clone()),
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

// ==================== 分块服务(search/revectorize) ====================

/// 按问题检索分块(向量+BM25 混合检索 RRF 融合 → 可选 rerank 精排 → 拼接上下文)
///
/// 对齐 Python service.search: 响应为 SearchResult 数组
/// (rid/content/metadata/score/previous_content/next_content/content_types)。
pub async fn search_by_question(
    state: &AppState,
    user_id: &str,
    req: crate::do_::document::SearchByQuestionRequest,
) -> Result<serde_json::Value, AppError> {
    use common::utils::db_vector as vector;

    // 1) 解析向量化模型并生成查询向量(query_content 在前拼接, 对齐 aembed_query 口径)
    let resolved = um_service::resolve_model(state, user_id, model_type::EMBEDDINGS).await?;
    let model_id = resolved.model_id.ok_or_else(|| {
        AppError::business("无可用向量化模型, 请在设置中绑定或由管理员配置默认向量化模型")
    })?;
    let target = module_ai::services::llm::get_llm(&state.db, &model_id, false)
        .await?
        .ok_or_else(|| AppError::business(format!("加载向量化模型失败: {model_id}")))?;
    let query_text = if req.query_content.is_empty() {
        req.query_text.clone()
    } else if req.query_text.is_empty() {
        req.query_content.clone()
    } else {
        format!("{}\n{}", req.query_content, req.query_text)
    };
    if query_text.trim().is_empty() {
        return Ok(serde_json::json!([]));
    }
    let vectors = module_ai::utils::llm::embed(&state.http, &target, &[query_text.clone()]).await?;
    let Some(query_vector) = vectors.into_iter().next() else {
        return Err(AppError::business("向量化模型未返回查询向量"));
    };

    // 2) 混合检索(稠密向量 + 稀疏 BM25, 服务端 RRF 融合)
    let client = vector::get(state)
        .await
        .ok_or_else(|| AppError::business("向量库未启用, 无法执行相似检索"))?;
    let mut hits = client
        .hybrid_search_chunks(&query_text, &query_vector, &req.project_ids, req.limit)
        .await
        .map_err(AppError::business)?;

    // 3) 可选 rerank 精排(引擎获取失败时降级保留 RRF 序, 不阻断检索)
    if req.enable_rerank && hits.len() > 1 {
        match module_ai::services::rerank::get_reranker(&state.db, None).await {
            Ok(engine) => {
                let texts: Vec<String> = hits.iter().map(|h| h.content.clone()).collect();
                let top_n = if req.rerank_limit > 0 {
                    Some(req.rerank_limit as usize)
                } else {
                    None
                };
                match engine
                    .arerank(&state.http, &query_text, &texts, top_n)
                    .await
                {
                    Ok(ranked) => {
                        let mut reindexed: Vec<vector::ChunkHit> = Vec::with_capacity(ranked.len());
                        for item in &ranked {
                            let idx = item
                                .get("index")
                                .and_then(|i| i.as_u64())
                                .map(|v| v as usize)
                                .unwrap_or(0);
                            let score = item
                                .get("relevance_score")
                                .or_else(|| item.get("score"))
                                .and_then(|s| s.as_f64())
                                .unwrap_or(0.0);
                            if let Some(mut hit) = hits.get(idx).cloned() {
                                hit.score = score;
                                reindexed.push(hit);
                            }
                        }
                        // 阈值仅过滤 rerank 归一化分数(0~1), 对齐 Python:
                        // score_threshold 只在 enable_rerank 时传入 _rerank 生效,
                        // 粗排(RRF 融合分约 1/61)不受该阈值影响
                        if req.score_threshold > 0.0 {
                            reindexed.retain(|h| h.score >= req.score_threshold);
                        }
                        hits = reindexed;
                    }
                    Err(e) => tracing::warn!("rerank 精排失败, 保留 RRF 排序: {e}"),
                }
            }
            Err(e) => tracing::warn!("rerank 引擎不可用, 保留 RRF 排序: {e}"),
        }
    }

    // 4) 拼接前后分块内容(同文档按 sort 定位, 对齐 Python previous/next_content)
    let results = build_search_results(state, hits).await?;
    Ok(serde_json::json!(results))
}

/// 检索命中 → 响应结构(查关系表补齐同文档前后分块文本)
///
/// 注: 分数阈值过滤已在 rerank 分支内完成(仅过滤归一化精排分), 此处不再过滤。
async fn build_search_results(
    state: &AppState,
    hits: Vec<common::utils::db_vector::ChunkHit>,
) -> Result<Vec<serde_json::Value>, AppError> {
    let mut results = Vec::with_capacity(hits.len());
    for hit in hits {
        let chunks = doc_dao::chunk_list_by_document(&state.db, &hit.document_id).await?;
        let index = chunks.iter().position(|c| c.id == hit.id);
        let (previous_content, next_content) = match index {
            Some(i) => (
                i.checked_sub(1).and_then(|p| chunks.get(p)).map(|c| c.content.clone()),
                chunks.get(i + 1).map(|c| c.content.clone()),
            ),
            None => (None, None),
        };
        results.push(serde_json::json!({
            "rid": hit.id,
            "content": hit.content,
            "metadata": hit.metadata,
            "score": hit.score,
            "previous_content": previous_content.unwrap_or_default(),
            "next_content": next_content.unwrap_or_default(),
            "content_types": hit.content_types,
        }));
    }
    Ok(results)
}

/// 全库重向量化任务执行体
///
/// 对齐 Python service.revectorize: 关系表全量分块 → 按新模型逐批向量化;
/// 集合维度与模型不一致时重建集合(旧向量随 drop 清空), 一致时原地 upsert。
pub async fn revectorize_all(
    state: &AppState,
    user_id: &str,
    model_id: Option<String>,
) -> Result<(), String> {
    use common::utils::db_vector as vector;

    // 1) 解析向量化模型(显式指定优先, 否则用户绑定→默认公共回退)
    let resolved = um_service::resolve_model(state, user_id, model_type::EMBEDDINGS)
        .await
        .map_err(|e| format!("解析向量化模型失败: {e}"))?;
    let mid = model_id
        .or(resolved.model_id)
        .ok_or("无可用向量化模型, 请先绑定或配置默认公共向量化模型")?;
    let target = module_ai::services::llm::get_llm(&state.db, &mid, false)
        .await
        .map_err(|e| format!("加载向量化模型失败: {e}"))?
        .ok_or_else(|| format!("向量化模型配置不存在: {mid}"))?;

    let client = vector::get(state)
        .await
        .ok_or("向量库未启用, 无法执行全库重向量化")?;

    // 2) 关系表全量分块(空库直接成功)
    let rows = doc_dao::chunk_list_all(&state.db)
        .await
        .map_err(|e| format!("读取分块失败: {e}"))?;
    if rows.is_empty() {
        return Ok(());
    }

    // 3) 维度探测: 首批向量确定目标维度, 与现有集合比对决定 upsert 或重建
    let first_batch: Vec<&project_document_chunk::Model> = rows.iter().take(16).collect();
    let first_texts: Vec<String> = first_batch.iter().map(|c| c.content.clone()).collect();
    let first_vectors = module_ai::utils::llm::embed(&state.http, &target, &first_texts)
        .await
        .map_err(|e| format!("向量化首批分块失败: {e}"))?;
    let new_dim = first_vectors
        .first()
        .map(|v| v.len() as i64)
        .unwrap_or(vector::DEFAULT_EMBEDDING_DIM);

    let exists = client
        .has_collection(vector::CHUNK_COLLECTION)
        .await
        .unwrap_or(false);
    if exists {
        let current_dim = client
            .collection_dim(vector::CHUNK_COLLECTION, "embedding")
            .await;
        if current_dim != Some(new_dim) {
            // 维度变更: 重建集合(对齐 Python drop_collection + create_table)
            client
                .drop_collection(vector::CHUNK_COLLECTION)
                .await
                .map_err(|e| format!("删除旧向量集合失败: {e}"))?;
            client
                .create_chunk_collection(new_dim)
                .await
                .map_err(|e| format!("重建向量集合失败: {e}"))?;
            tracing::info!("向量集合维度变更 {current_dim:?} → {new_dim}, 已重建");
        }
    } else {
        client
            .create_chunk_collection(new_dim)
            .await
            .map_err(|e| format!("创建向量集合失败: {e}"))?;
    }

    // 4) 逐批向量化并写入(首批复用探测结果)
    let mut written = 0usize;
    let mut vector_rows: Vec<vector::ChunkRow> = first_batch
        .iter()
        .zip(first_vectors.iter())
        .map(|(c, vec)| chunk_model_to_row(c, vec))
        .collect();
    client
        .upsert_chunks(std::mem::take(&mut vector_rows))
        .await
        .map_err(|e| format!("向量写入失败: {e}"))?;
    written += first_batch.len();

    for batch in rows.iter().skip(16).collect::<Vec<_>>().chunks(16) {
        let texts: Vec<String> = batch.iter().map(|c| c.content.clone()).collect();
        let vectors = module_ai::utils::llm::embed(&state.http, &target, &texts)
            .await
            .map_err(|e| format!("向量化失败(第 {} 条起): {e}", written))?;
        let rows_to_write: Vec<vector::ChunkRow> = batch
            .iter()
            .zip(vectors.iter())
            .map(|(c, vec)| chunk_model_to_row(c, vec))
            .collect();
        client
            .upsert_chunks(rows_to_write)
            .await
            .map_err(|e| format!("向量写入失败(第 {} 条起): {e}", written))?;
        written += batch.len();
        tracing::info!("全库重向量化进度: {}/{}", written, rows.len());
    }
    tracing::info!("全库重向量化完成: 共 {written} 条");
    Ok(())
}

/// 关系表分块模型 → 向量库写入行
fn chunk_model_to_row(
    c: &project_document_chunk::Model,
    vec: &[f64],
) -> common::utils::db_vector::ChunkRow {
    common::utils::db_vector::ChunkRow {
        id: c.id.clone(),
        sort: c.sort as i64,
        document_id: c.document_id.clone(),
        project_id: c.project_id.clone(),
        content: c.content.clone(),
        source: c.source.clone(),
        content_types: json_str_list(&c.content_types),
        position: c.position.clone(),
        metadata: c.metadata.clone().unwrap_or(serde_json::json!({})),
        embedding: vec.to_vec(),
    }
}
