//! 文档与分块 DTO(对齐 Python module_rag/do/project_document.py、
//! project_document_chunk.py), 含文件类型白名单与入库流水线注册表。

use sea_orm::prelude::{DateTimeWithTimeZone, Json};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

use crate::do_::entity::project_document;

// ==================== 文件类型白名单(DocType) ====================

/// 文档类扩展名
pub const DOCUMENT_TYPES: [&str; 7] = ["pdf", "docx", "xlsx", "pptx", "txt", "md", "csv"];
/// 代码类扩展名
pub const CODE_TYPES: [&str; 2] = ["py", "java"];
/// 图片类扩展名
pub const IMAGE_TYPES: [&str; 4] = ["png", "jpg", "jpeg", "tiff"];
/// 音频类扩展名
pub const AUDIO_TYPES: [&str; 2] = ["mp3", "wav"];
/// 视频类扩展名
pub const VIDEO_TYPES: [&str; 2] = ["mp4", "avi"];

/// 允许上传的扩展名全量集合(不含点)
pub const ALLOWED_EXTENSIONS: [&str; 17] = [
    "pdf", "docx", "xlsx", "pptx", "txt", "md", "csv", "py", "java", "png", "jpg", "jpeg", "tiff",
    "mp3", "wav", "mp4", "avi",
];

/// 判断文件扩展名(不含点)是否允许上传
pub fn is_allowed_extension(ext: &str) -> bool {
    ALLOWED_EXTENSIONS.contains(&ext)
}

/// 文本类扩展名(解析管线可原生读取的格式; pdf/docx 等二进制格式需专用解析引擎)
pub fn is_text_extension(ext: &str) -> bool {
    matches!(ext, "txt" | "md" | "csv" | "py" | "java")
}

// ==================== 入库流水线注册表(INGEST_PIPELINE) ====================

/// 流水线步骤定义(有序注册表条目)
#[derive(Debug, Clone, Serialize)]
pub struct IngestStepSpec {
    /// 步骤编码(parse/chunk/embed/graph/tag/web_merge)
    pub step: &'static str,
    /// 步骤显示名
    pub name: &'static str,
    /// 步骤说明
    pub description: &'static str,
    /// 总进度权重(预留步骤 0)
    pub weight: f64,
    /// 是否已启用(预留步骤 false, 不参与进度计算)
    pub enabled: bool,
}

/// 文档入库流水线注册表(对齐 Python INGEST_PIPELINE; 预留步骤占位不计权重)
pub const INGEST_PIPELINE: [IngestStepSpec; 6] = [
    IngestStepSpec { step: "parse", name: "解析", description: "OCR/文本提取, 文件转为原始内容块", weight: 40.0, enabled: true },
    IngestStepSpec { step: "chunk", name: "拆分chunk", description: "分块策略识别与重分块", weight: 20.0, enabled: true },
    IngestStepSpec { step: "embed", name: "向量化", description: "内容块向量化并写入向量库", weight: 40.0, enabled: true },
    IngestStepSpec { step: "graph", name: "图谱化", description: "知识图谱构建(预留)", weight: 0.0, enabled: false },
    IngestStepSpec { step: "tag", name: "标签抽取", description: "关键词/标签提取(预留)", weight: 0.0, enabled: false },
    IngestStepSpec { step: "web_merge", name: "网络检索合并", description: "外部网络检索结果融合(预留)", weight: 0.0, enabled: false },
];

/// 单个入库步骤的进度(注册表定义 + 文档已存储状态合并结果)
#[derive(Debug, Clone, Serialize)]
pub struct IngestStepProgress {
    pub step: String,
    pub name: String,
    pub description: String,
    pub enabled: bool,
    pub weight: f64,
    pub status: String,
    pub progress: f64,
    pub message: Option<String>,
    pub error: Option<String>,
}

/// 文档入库步骤与进度响应(GET /{document_id}/progress)
#[derive(Debug, Serialize)]
pub struct DocumentIngestProgress {
    pub document_id: String,
    pub parse_status: String,
    /// 总进度 0~100(按启用步骤权重加权)
    pub progress: f64,
    pub steps: Vec<IngestStepProgress>,
}

/// 从 parse_steps JSON 中读取指定步骤的状态字典(缺省空)
fn step_state(parse_steps: &Json, step: &str) -> Value {
    parse_steps.get(step).cloned().unwrap_or_else(|| json!({}))
}

/// 流水线注册表与文档已存储的步骤状态合并(未记录的步骤按 pending 展示)
pub fn merge_ingest_steps(parse_steps: &Json) -> Vec<IngestStepProgress> {
    INGEST_PIPELINE
        .iter()
        .map(|spec| {
            let state = step_state(parse_steps, spec.step);
            IngestStepProgress {
                step: spec.step.to_string(),
                name: spec.name.to_string(),
                description: spec.description.to_string(),
                enabled: spec.enabled,
                weight: spec.weight,
                status: state
                    .get("status")
                    .and_then(Value::as_str)
                    .unwrap_or("pending")
                    .to_string(),
                progress: state.get("progress").and_then(Value::as_f64).unwrap_or(0.0),
                message: state
                    .get("message")
                    .and_then(Value::as_str)
                    .map(str::to_string),
                error: state.get("error").and_then(Value::as_str).map(str::to_string),
            }
        })
        .collect()
}

/// 按启用步骤权重计算总进度(预留步骤不计入; completed 兜底 100)
pub fn compute_ingest_progress(parse_steps: &Json) -> f64 {
    let total_weight: f64 = INGEST_PIPELINE.iter().filter(|s| s.enabled).map(|s| s.weight).sum();
    if total_weight <= 0.0 {
        return 0.0;
    }
    let mut acc = 0.0;
    for spec in INGEST_PIPELINE.iter().filter(|s| s.enabled) {
        let state = step_state(parse_steps, spec.step);
        let mut progress = state.get("progress").and_then(Value::as_f64).unwrap_or(0.0);
        if state.get("status").and_then(Value::as_str) == Some("completed") {
            progress = 100.0;
        }
        acc += spec.weight * progress.clamp(0.0, 100.0) / 100.0;
    }
    (acc / total_weight * 100.0 * 10.0).round() / 10.0
}

// ==================== 文档请求/响应 ====================

/// 更新文档请求(None=不更新)
#[derive(Debug, Default, Deserialize)]
pub struct ProjectDocumentUpdate {
    #[serde(default)]
    pub name: Option<String>,
    #[serde(default)]
    pub description: Option<String>,
}

/// 项目文档响应(字段与 Python ProjectDocumentResponse 一致)
#[derive(Debug, Serialize)]
pub struct ProjectDocumentResponse {
    pub id: String,
    pub project_id: String,
    pub name: String,
    pub file_extension: String,
    pub mime_type: Option<String>,
    pub file_size_bytes: i32,
    pub physical_path: String,
    pub content_hash: Option<String>,
    pub entry_id: Option<String>,
    pub description: Option<String>,
    pub parse_status: String,
    pub chunk_count: i32,
    pub error_message: Option<String>,
    /// 入库步骤进度 JSONB
    pub parse_steps: Json,
    /// 上传后自动解析任务派发警告(仅上传接口返回)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub parse_task_warning: Option<String>,
    pub uploaded_by: String,
    pub created_at: Option<DateTimeWithTimeZone>,
    pub updated_at: DateTimeWithTimeZone,
}

impl From<project_document::Model> for ProjectDocumentResponse {
    fn from(m: project_document::Model) -> Self {
        Self {
            id: m.id,
            project_id: m.project_id,
            name: m.name,
            file_extension: m.file_extension,
            mime_type: m.mime_type,
            file_size_bytes: m.file_size_bytes,
            physical_path: m.physical_path,
            content_hash: m.content_hash,
            entry_id: m.entry_id,
            description: m.description,
            parse_status: m.parse_status,
            chunk_count: m.chunk_count,
            error_message: m.error_message,
            parse_steps: m.parse_steps,
            parse_task_warning: None,
            uploaded_by: m.uploaded_by,
            created_at: m.created_at,
            updated_at: m.updated_at,
        }
    }
}

/// 条目浏览项(项目文档目录树条目 + 联查文档解析口径, 对齐 Python list_entries)
#[derive(Debug, Serialize)]
pub struct DocumentEntryItem {
    pub id: String,
    pub pid: Option<String>,
    pub name: String,
    pub is_directory: bool,
    pub file_size_bytes: Option<i64>,
    pub file_extension: Option<String>,
    pub mime_type: Option<String>,
    pub description: Option<String>,
    pub created_at: Option<DateTimeWithTimeZone>,
    pub updated_at: DateTimeWithTimeZone,
    /// 目录命中文档记录时的解析口径字段(文件条目为 null)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub document_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub parse_status: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub chunk_count: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error_message: Option<String>,
}

/// 解析状态合法值(列表过滤参数校验)
pub fn is_valid_parse_status(status: &str) -> bool {
    matches!(status, "pending" | "parsing" | "completed" | "failed")
}

// ==================== 分块检索/重向量化 ====================

/// 按问题检索请求(POST /project-document-chunks/search-by-question)
#[derive(Debug, Deserialize)]
pub struct SearchByQuestionRequest {
    pub project_ids: Vec<String>,
    #[serde(default = "d_query_content")]
    pub query_content: String,
    #[serde(default)]
    pub query_text: String,
    #[serde(default = "d_limit")]
    pub limit: i64,
    #[serde(default = "d_threshold")]
    pub score_threshold: f64,
    #[serde(default)]
    pub enable_rerank: bool,
    #[serde(default = "d_rerank_limit")]
    pub rerank_limit: i64,
}

fn d_query_content() -> String {
    String::new()
}

fn d_limit() -> i64 {
    2
}

fn d_threshold() -> f64 {
    0.5
}

fn d_rerank_limit() -> i64 {
    10
}

/// 全库重向量化请求(仅系统管理员)
#[derive(Debug, Default, Deserialize)]
pub struct RevectorizeRequest {
    #[serde(default)]
    pub model_id: Option<String>,
}

/// 重向量化任务受理响应(202)
#[derive(Debug, Serialize)]
pub struct RevectorizeAccepted {
    pub task_id: String,
    pub message: String,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn 扩展名白名单判断() {
        assert!(is_allowed_extension("pdf"));
        assert!(is_allowed_extension("java"));
        assert!(!is_allowed_extension("exe"));
        // 文本类可原生读取; 二进制类需专用解析引擎
        for ext in ["txt", "md", "csv", "py", "java"] {
            assert!(is_text_extension(ext));
        }
        assert!(!is_text_extension("pdf"));
        assert!(!is_text_extension("png"));
    }

    #[test]
    fn 流水线步骤合并_未记录按pending() {
        let steps = merge_ingest_steps(&json!({}));
        assert_eq!(steps.len(), 6);
        assert!(steps.iter().all(|s| s.status == "pending" && s.progress == 0.0));
        // 预留步骤 enabled=false 不计权重
        let disabled: Vec<_> = steps.iter().filter(|s| !s.enabled).collect();
        assert_eq!(disabled.len(), 3);
        let total: f64 = steps.iter().filter(|s| s.enabled).map(|s| s.weight).sum();
        assert_eq!(total, 100.0);
    }

    #[test]
    fn 入库总进度加权计算() {
        // parse 完成(40) + chunk 进行中(20*50%) = 50
        let p = compute_ingest_progress(&json!({
            "parse": {"status": "completed", "progress": 100.0},
            "chunk": {"status": "running", "progress": 50.0},
        }));
        assert_eq!(p, 50.0);
        // 全部完成 = 100
        let full = compute_ingest_progress(&json!({
            "parse": {"status": "completed"}, "chunk": {"status": "completed"}, "embed": {"status": "completed"},
        }));
        assert_eq!(full, 100.0);
        // 空状态 = 0
        assert_eq!(compute_ingest_progress(&json!({})), 0.0);
    }

    #[test]
    fn 解析状态过滤参数校验() {
        for s in ["pending", "parsing", "completed", "failed"] {
            assert!(is_valid_parse_status(s));
        }
        assert!(!is_valid_parse_status("unknown"));
    }
}
