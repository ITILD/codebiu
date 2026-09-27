//! 存储接口协议 + 工厂 + 全局单例(对齐 Python utils/multi_storage)
//!
//! 根目录语义:
//! - local: 物理键相对 base_dir 解析(base_dir/key)
//! - s3:    物理键相对 bucket 解析(bucket/key)

pub mod local;
pub mod s3;

use std::sync::Arc;
use std::time::Duration;

use async_trait::async_trait;
use bytes::Bytes;
use futures::future::BoxFuture;
use tokio::sync::OnceCell;

use common::config::dynamic::FileSystemSettings;
use common::runtime::AppState;
use common::utils::error::AppError;

use crate::do_::storage::{StorageConfig, StorageType};

/// 分片信息(存储接口通用结构, 对齐 Python {"part_number", "etag", "size"})
#[derive(Debug, Clone)]
pub struct PartInfo {
    pub part_number: i64,
    pub etag: String,
    pub size: i64,
}

/// 分片合并结果(content_hash, file_size_bytes, final_key)
pub type CompleteResult = (String, i64, String);

/// 存储接口协议(local 与 s3/rustfs 等对象存储实现保持一致)
#[async_trait]
pub trait Storage: Send + Sync {
    /// 存储类型标识(日志/统计展示用, 小写: local/s3)
    fn kind(&self) -> &'static str;

    /// 保存数据到存储中
    async fn save(&self, key: &str, data: &[u8]) -> Result<(), AppError>;

    /// 从存储中加载数据
    async fn load(&self, key: &str) -> Result<Bytes, AppError>;

    /// 流式分块读取存储内容(大文件下载避免全量载入内存)
    fn stream(
        &self,
        key: &str,
        chunk_size: usize,
    ) -> BoxFuture<'static, Result<futures::stream::BoxStream<'static, Result<Bytes, std::io::Error>>, AppError>>;

    /// 删除指定键的数据(不存在也视为失败返回 false)
    async fn delete(&self, key: &str) -> bool;

    /// 检查键是否存在
    async fn exists(&self, key: &str) -> bool;

    /// 是否支持预签名直传(S3 协议存储支持, 本地磁盘必须中转)
    fn supports_presign(&self) -> bool;

    /// 初始化分片上传会话, 返回 upload_id
    async fn create_multipart(&self, key: &str, content_type: &str) -> Result<String, AppError>;

    /// 上传单个分片
    async fn upload_part(
        &self,
        key: &str,
        upload_id: &str,
        part_number: i64,
        data: &[u8],
    ) -> Result<PartInfo, AppError>;

    /// 查询会话中已上传的分片列表(断点续传)
    async fn list_parts(&self, key: &str, upload_id: &str) -> Result<Vec<PartInfo>, AppError>;

    /// 按序合并分片为最终文件(内容哈希去重命名)
    ///
    /// :param parts: 分片清单(按上传顺序)
    /// :param expected_hash: 调用方声明的内容SHA-256(前端直传场景服务端无法重算, 以此归位;
    ///                       本地存储可重算时以真实哈希为准)
    /// :return: (content_hash, file_size_bytes, final_key)
    async fn complete_multipart(
        &self,
        key: &str,
        upload_id: &str,
        parts: &[PartInfo],
        expected_hash: Option<&str>,
    ) -> Result<CompleteResult, AppError>;

    /// 取消分片上传会话并清理已上传分片
    async fn abort_multipart(&self, key: &str, upload_id: &str) -> Result<(), AppError>;

    /// 生成预签名上传URL(前端直传用, 不经过服务端; 不支持返回 None)
    async fn presign_put(
        &self,
        key: &str,
        upload_id: Option<&str>,
        part_number: Option<i64>,
        expires: u64,
    ) -> Result<Option<String>, AppError>;

    /// 生成预签名下载URL(前端直连下载用; 不支持返回 None)
    async fn presign_get(
        &self,
        key: &str,
        expires: u64,
        download_filename: Option<&str>,
    ) -> Result<Option<String>, AppError>;

    /// 启动期就绪检查(S3: 建桶+CORS; local: 目录就绪)
    async fn ensure_ready(&self) -> Result<(), AppError> {
        Ok(())
    }
}

/// 工厂: 按配置类型构建存储实例(对齐 Python StorageFactory.create)
pub fn create(config: StorageConfig) -> Arc<dyn Storage> {
    match config {
        StorageConfig::Local(c) => Arc::new(local::LocalStorage::new(c)),
        StorageConfig::S3(c) => Arc::new(s3::S3Storage::new(c)),
    }
}

// ==================== 全局存储单例(对齐 Python config/filesystem.py 的 storage 惰性属性) ====================

/// 存储配置单例(对齐 Python config/filesystem.py 的 storage_config 惰性属性)
static STORAGE_CONFIG: OnceCell<StorageConfig> = OnceCell::const_new();

/// 预签名 URL 默认有效期(秒)
pub const PRESIGN_EXPIRES: u64 = 3600;

/// 全局上传目录(对齐 Python DIR_UPLOAD: dir.base / dir.base_child.upload)
fn upload_dir(state: &AppState) -> std::path::PathBuf {
    std::path::Path::new(&state.config.dir.base).join(&state.config.dir.base_child.upload)
}

/// 获取存储配置单例(首次访问时按动态配置装配, 幂等)
pub async fn config(state: &AppState) -> Result<StorageConfig, AppError> {
    STORAGE_CONFIG
        .get_or_try_init(|| async {
            let fs: FileSystemSettings = state.settings.get("file_system").await?;
            StorageConfig::from_settings(&fs, upload_dir(state))
        })
        .await
        .cloned()
}

/// 获取全局存储单例(首次访问时按动态配置装配, 幂等)
///
/// 与 Python 启动钩子装配时机不同: 此处惰性初始化(首次请求/启动钩子触发均可)
pub async fn get(state: &AppState) -> Result<Arc<dyn Storage>, AppError> {
    Ok(create(config(state).await?))
}

/// 启动钩子: 确保物理存储就绪(S3 协议存储桶不存在时自动创建并配置 CORS)
///
/// 失败仅告警不阻断启动(上传时会再次暴露具体错误), 对齐 Python ensure_storage_ready
pub async fn ensure_ready(state: &AppState) {
    match get(state).await {
        Ok(s) => {
            if let Err(e) = s.ensure_ready().await {
                tracing::warn!("存储桶检查/自动创建失败: {e}");
            } else {
                tracing::info!("物理存储就绪: type={}", s.kind());
            }
        }
        Err(e) => tracing::warn!("存储配置装配失败: {e}"),
    }
}

/// 按类型构建临时存储实例(存储迁移/双存储搬运用, 与全局单例互不影响)
pub async fn build_for(state: &AppState, storage_type: StorageType) -> Result<Arc<dyn Storage>, AppError> {
    let fs: FileSystemSettings = state.settings.get("file_system").await?;
    // 以指定类型覆盖装配(迁移目标可能与当前配置不同)
    let mut fs2 = fs.clone();
    fs2.storage_type = storage_type.as_str().to_string();
    let cfg = StorageConfig::from_settings(&fs2, upload_dir(state))?;
    Ok(create(cfg))
}

/// ETag 去引号(S3 返回 "..." 形式, 对账与合并时统一剥除, 与 Python strip('"') 一致)
pub fn strip_etag_quotes(etag: &str) -> String {
    etag.trim_matches('"').to_string()
}

/// 预签名有效期转 Duration
pub fn presign_ttl(expires: u64) -> Duration {
    Duration::from_secs(expires.max(1))
}
