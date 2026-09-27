//! 文件系统条目/内容 DO 层(对齐 Python module_file/do/filesystem.py)
//!
//! 实体 crate::do_::entity::file_entry / crate::do_::entity::file_content 为表模型;
//! 本文件定义 API 请求/响应 DTO 与内部创建/更新结构(非数据库三件套)。

use chrono::{DateTime, Utc};
use crate::do_::entity::sea_orm_active_enums::{Storagetype, Taskstatus};
use crate::do_::entity::{file_content, file_entry};
use sea_orm::prelude::{DateTimeWithTimeZone, Json};
use serde::{Deserialize, Serialize};

use crate::do_::storage::StorageType;

/// 状态枚举 → 前端小写字符串(Python TaskStatus StrEnum 序列化为值, 前端按小写展示)
pub fn task_status_str(s: &Taskstatus) -> &'static str {
    match s {
        Taskstatus::Pending => "pending",
        Taskstatus::Running => "running",
        Taskstatus::Paused => "paused",
        Taskstatus::Success => "success",
        Taskstatus::Failed => "failed",
        Taskstatus::Cancelled => "cancelled",
        Taskstatus::Expired => "expired",
    }
}

/// 存储类型枚举 → 前端小写字符串(Python StorageType StrEnum 序列化为值)
pub fn storage_type_enum_str(s: &Storagetype) -> &'static str {
    match s {
        Storagetype::Local => "local",
        Storagetype::S3 => "s3",
    }
}

/// 当前 UTC 时间(实体时间戳填充用)
pub fn now_utc() -> DateTimeWithTimeZone {
    Utc::now().into()
}

/// JSON 列(tags) → 字符串数组(空值归一化为空数组, 与 Python FileEntryDetail 口径一致)
pub fn json_to_tags(v: &Option<Json>) -> Vec<String> {
    match v {
        Some(serde_json::Value::Array(items)) => items
            .iter()
            .filter_map(|i| i.as_str().map(|s| s.to_string()))
            .collect(),
        _ => Vec::new(),
    }
}

/// 字符串数组 → JSON 列(tags)
pub fn tags_to_json(tags: &[String]) -> Json {
    serde_json::Value::Array(
        tags.iter()
            .map(|t| serde_json::Value::String(t.clone()))
            .collect(),
    )
    .into()
}

/// 文件/目录条目响应(字段与 Python FileEntry 模型序列化完全一致)
#[derive(Debug, Clone, Serialize)]
pub struct FileEntryResp {
    pub id: String,
    pub pid: Option<String>,
    pub name: String,
    pub logical_path: String,
    pub is_directory: bool,
    /// 内容哈希(仅文件)
    pub content_hash: Option<String>,
    /// 来源模块标记(rag/avatar 等业务条目; NULL=文件管理自有条目)
    pub source_module: Option<String>,
    pub file_size_bytes: Option<i64>,
    pub file_extension: Option<String>,
    pub mime_type: Option<String>,
    pub description: Option<String>,
    /// 关键词标签组(默认空)
    pub tags: Vec<String>,
    pub is_active: bool,
    pub user_id: Option<String>,
    pub group_id: Option<String>,
    /// 条目状态(小写字符串)
    pub entry_status: Option<String>,
    pub created_at: Option<DateTimeWithTimeZone>,
    pub updated_at: DateTimeWithTimeZone,
}

impl From<file_entry::Model> for FileEntryResp {
    fn from(m: file_entry::Model) -> Self {
        Self {
            id: m.id,
            pid: m.pid,
            name: m.name,
            logical_path: m.logical_path,
            is_directory: m.is_directory,
            content_hash: m.content_hash,
            source_module: m.source_module,
            file_size_bytes: m.file_size_bytes.map(|v| v as i64),
            file_extension: m.file_extension,
            mime_type: m.mime_type,
            description: m.description,
            tags: json_to_tags(&m.tags),
            is_active: m.is_active,
            user_id: m.user_id,
            group_id: m.group_id,
            entry_status: m.entry_status.as_ref().map(|s| task_status_str(s).to_string()),
            created_at: m.created_at,
            updated_at: m.updated_at,
        }
    }
}

/// 条目详情视图(详情按钮用): 条目 + 内容元数据 + 上传用户名
///
/// 对齐 Python FileEntryDetail(FileEntryWithContent + owner_name)
#[derive(Debug, Clone, Serialize)]
pub struct FileEntryDetailResp {
    #[serde(flatten)]
    pub entry: FileEntryResp,
    /// 物理存储相对位置(仅文件)
    pub physical_storage: Option<String>,
    /// 内容引用计数(仅文件)
    pub ref_count: Option<i64>,
    /// 物理存储类型(local/s3, 仅文件)
    pub storage_type: Option<String>,
    /// 内容状态(仅文件)
    pub content_status: Option<String>,
    /// 上传用户名(昵称优先, 其次用户名)
    pub owner_name: Option<String>,
}

/// 条目更新请求(名称/描述/标签可改; 名称变更走重命名逻辑)
#[derive(Debug, Clone, Deserialize)]
pub struct FileEntryUpdateReq {
    pub name: Option<String>,
    pub description: Option<String>,
    pub tags: Option<Vec<String>>,
}

/// 条目内部创建结构(dao 层落库用; 与 Python FileEntryCreate 对齐)
#[derive(Debug, Clone, Default)]
pub struct FileEntryCreate {
    pub name: String,
    pub pid: Option<String>,
    pub logical_path: String,
    pub is_directory: bool,
    pub content_hash: Option<String>,
    pub file_size_bytes: Option<i64>,
    pub file_extension: Option<String>,
    pub mime_type: Option<String>,
    pub description: Option<String>,
    pub tags: Vec<String>,
    /// 来源模块 key(业务模块条目标记; 创建时从父目录继承)
    pub source_module: Option<String>,
    pub user_id: Option<String>,
}

/// 条目内部更新补丁(dao 层用; None=不更新, 双层 Option 支持显式置空)
#[derive(Debug, Clone, Default)]
pub struct FileEntryPatch {
    pub name: Option<String>,
    pub logical_path: Option<String>,
    /// Some(None) 表示置空(移回根目录)
    pub pid: Option<Option<String>>,
    pub description: Option<Option<String>>,
    pub tags: Option<Vec<String>>,
}

/// 文件内容内部创建结构(对齐 Python FileContentCreate)
#[derive(Debug, Clone)]
pub struct FileContentCreate {
    pub content_hash: String,
    pub physical_storage: String,
    pub file_size_bytes: i64,
    /// rustfs 与 s3 行为一致, 统一落 S3(表枚举仅 LOCAL/S3)
    pub storage_type: Storagetype,
}

/// 文件内容内部更新补丁(对齐 Python FileContentUpdate)
#[derive(Debug, Clone, Default)]
pub struct FileContentPatch {
    pub physical_storage: Option<String>,
    pub file_size_bytes: Option<i64>,
    pub storage_type: Option<Storagetype>,
}

/// 文件内容响应(内容元数据, 对齐 Python FileContent)
#[derive(Debug, Clone, Serialize)]
pub struct FileContentResp {
    pub content_hash: String,
    pub physical_storage: Option<String>,
    pub file_size_bytes: Option<i64>,
    pub ref_count: i32,
    pub storage_type: Option<String>,
    pub content_status: Option<String>,
}

impl From<file_content::Model> for FileContentResp {
    fn from(m: file_content::Model) -> Self {
        Self {
            content_hash: m.content_hash,
            physical_storage: m.physical_storage,
            file_size_bytes: m.file_size_bytes.map(|v| v as i64),
            ref_count: m.ref_count,
            storage_type: m.storage_type.as_ref().map(|s| storage_type_enum_str(s).to_string()),
            content_status: m.content_status.as_ref().map(|s| task_status_str(s).to_string()),
        }
    }
}

// ==================== 分片上传(multipart)模型 ====================

/// 初始化分片上传请求
#[derive(Debug, Deserialize)]
pub struct MultipartInitRequest {
    pub filename: String,
    pub content_type: Option<String>,
    /// 文件总大小(字节)
    pub file_size_bytes: i64,
    /// 文件内容 SHA-256(前端计算)
    pub content_hash: String,
    /// 父目录ID(为空上传到根目录)
    pub pid: Option<String>,
    pub description: Option<String>,
}

/// 分片信息
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MultipartPartInfo {
    /// 分片号(从1开始)
    pub part_number: i64,
    /// 分片ETag(S3返回, 合并校验用)
    #[serde(default)]
    pub etag: String,
    /// 分片大小(字节)
    #[serde(default)]
    pub size: i64,
}

/// 初始化分片上传响应
#[derive(Debug, Serialize)]
pub struct MultipartInitResponse {
    /// 内容已存在(秒传, 直接建条目)
    pub is_existing: bool,
    /// 分片上传会话凭证(签名token, 秒传时为None)
    pub upload_id: Option<String>,
    /// 建议分片大小(字节, 最后一片可小于该值)
    pub part_size: i64,
    /// 上传模式: direct=预签名直传S3(前端直连) / proxy=服务端中转(local)
    pub mode: String,
    /// direct模式专用: 每片的预签名上传URL(下标=分片号-1); proxy模式为None
    pub part_urls: Option<Vec<String>>,
}

/// 完成分片上传请求
#[derive(Debug, Deserialize)]
pub struct MultipartCompleteRequest {
    pub filename: String,
    pub pid: Option<String>,
    pub description: Option<String>,
    /// 文件总大小(完整性校验)
    pub file_size_bytes: Option<i64>,
    /// 已上传分片列表
    pub parts: Vec<MultipartPartInfo>,
}

/// 上传模式查询响应(前端上传前获取, 决定直传/中转策略)
#[derive(Debug, Serialize)]
pub struct UploadModeResponse {
    /// 上传模式: direct=预签名直传 / proxy=服务端中转
    pub mode: String,
    /// 分片大小(字节)
    pub part_size: i64,
    /// proxy模式下小文件直传上限(MB)
    pub max_size: i64,
}

/// 内容已存在(秒传)时创建文件条目请求
#[derive(Debug, Deserialize)]
pub struct EntryCreateRequest {
    pub name: String,
    pub pid: Option<String>,
    /// 内容SHA-256
    pub content_hash: String,
    pub file_size_bytes: i64,
    pub mime_type: Option<String>,
    pub description: Option<String>,
}

/// 批量删除请求(文件与目录混选, 目录递归删除)
#[derive(Debug, Deserialize)]
pub struct BatchDeleteRequest {
    pub entry_ids: Vec<String>,
}

/// 批量删除单项失败信息
#[derive(Debug, Serialize)]
pub struct BatchDeleteItemError {
    pub id: String,
    pub error: String,
}

/// 批量删除结果
#[derive(Debug, Serialize)]
pub struct BatchDeleteResult {
    pub deleted: i64,
    pub failed: Vec<BatchDeleteItemError>,
}

/// 批量探测条目下载权限请求(前端下载按钮灰显用)
#[derive(Debug, Deserialize)]
pub struct DownloadPermsRequest {
    /// 条目ID列表(上限200)
    pub entry_ids: Vec<String>,
}

/// 存储统计信息(管理视图, 对齐 Python StorageStats)
#[derive(Debug, Serialize)]
pub struct StorageStats {
    /// 当前生效的存储类型(local/s3/rustfs)
    pub storage_type: String,
    /// 逻辑条目总数(含目录)
    pub entry_total: i64,
    /// 文件条目数
    pub file_total: i64,
    /// 目录条目数
    pub folder_total: i64,
    /// 物理内容记录数(按内容哈希去重后)
    pub content_total: i64,
    /// 物理存储总占用(字节, 去重后)
    pub used_bytes: i64,
}

/// 存储迁移请求(把旧存储的物理内容搬运到新存储, 逻辑条目不变)
#[derive(Debug, Deserialize)]
pub struct MigrateRequest {
    /// 源存储类型(旧数据所在存储)
    pub from_type: StorageType,
    /// 目标存储类型(迁移目的地)
    pub to_type: StorageType,
}

/// 存储迁移单项失败
#[derive(Debug, Serialize)]
pub struct MigrateItemError {
    pub content_hash: String,
    pub error: String,
}

/// 存储迁移结果
#[derive(Debug, Serialize)]
pub struct MigrateResult {
    pub total: usize,
    pub migrated: i64,
    pub skipped: i64,
    pub failed: Vec<MigrateItemError>,
}

/// 字符串长度校验(FastAPI Query/Field min_length/max_length 等价, 违规 → 422)
pub fn check_len(loc: &[&str], value: &str, min: usize, max: usize) -> Result<(), crate::do_::LenError> {
    let n = value.chars().count();
    if n < min {
        return Err(crate::do_::LenError::new(
            loc,
            if min == max {
                format!("String should have {min} characters")
            } else {
                format!("String should have at least {min} character")
            },
        ));
    }
    if n > max {
        return Err(crate::do_::LenError::new(
            loc,
            format!("String should have at most {max} characters"),
        ));
    }
    Ok(())
}

/// 长度校验错误(loc 转换需要所有权, 便于控制器直接 `?`)
#[derive(Debug)]
pub struct LenError {
    pub loc: Vec<String>,
    pub msg: String,
}

impl LenError {
    pub fn new(loc: &[&str], msg: String) -> Self {
        Self {
            loc: loc.iter().map(|s| s.to_string()).collect(),
            msg,
        }
    }
}

impl From<LenError> for common::utils::error::AppError {
    fn from(e: LenError) -> Self {
        common::utils::error::AppError::Validation(vec![
            common::utils::error::ValidationErrorItem {
                loc: e.loc,
                msg: e.msg,
                error_type: "value_error".to_string(),
            },
        ])
    }
}

/// 数值范围校验(FastAPI ge/le 等价, 违规 → 422)
pub fn check_range(loc: &[&str], value: i64, min: i64, max: i64) -> Result<(), LenError> {
    if value < min || value > max {
        let msg = if value < min {
            format!("Input should be greater than or equal to {min}")
        } else {
            format!("Input should be less than or equal to {max}")
        };
        return Err(LenError::new(loc, msg));
    }
    Ok(())
}

/// 日期字符串: 本地当天 YYYYMMDD(物理键日期分目录用, 与 Python strftime 一致)
pub fn today_key() -> String {
    DateTime::<Utc>::from(std::time::SystemTime::now()).format("%Y%m%d").to_string()
}
