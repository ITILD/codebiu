//! 存储类型与配置 DO 层(对齐 Python module_file/utils/multi_storage/do/storage_config.py)

use common::config::dynamic::FileSystemSettings;
use common::utils::error::AppError;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;

use crate::do_::LenError;

/// 存储类型(local/s3/rustfs)
///
/// rustfs 为 S3 兼容开源对象存储, 复用 S3 配置与实现(仅枚举别名, 行为一致)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum StorageType {
    Local,
    S3,
    Rustfs,
}

impl StorageType {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Local => "local",
            Self::S3 => "s3",
            Self::Rustfs => "rustfs",
        }
    }

    /// 字符串解析(非法值 → 422, 对齐 pydantic Literal 校验)
    pub fn parse(s: &str) -> Result<Self, LenError> {
        match s {
            "local" => Ok(Self::Local),
            "s3" => Ok(Self::S3),
            "rustfs" => Ok(Self::Rustfs),
            _ => Err(LenError::new(
                &["body", "storage_type"],
                format!("Input should be 'local', 's3' or 'rustfs', got '{s}'"),
            )),
        }
    }
}

/// 存储基础限额(各存储配置共用; 字段名与 file_system 动态配置保持一致)
#[derive(Debug, Clone)]
pub struct StorageLimits {
    /// 单文件最大存储(MB)
    pub max_size: f64,
    /// 允许的 MIME 类型列表(支持 image/* 通配), 空 = 不限制
    pub allowed_extensions: Vec<String>,
}

impl StorageLimits {
    /// 最大字节数
    pub fn max_size_bytes(&self) -> usize {
        (self.max_size * 1024.0 * 1024.0) as usize
    }

    /// 校验 MIME 类型是否在允许列表内
    ///
    /// 允许列表为空返回 true; 否则按精确/通配(image/*)匹配
    pub fn is_mime_allowed(&self, mime_type: Option<&str>) -> bool {
        if self.allowed_extensions.is_empty() {
            return true;
        }
        let Some(mime) = mime_type else {
            return false;
        };
        let mime = mime.to_lowercase();
        self.allowed_extensions.iter().any(|pattern| {
            let p = pattern.to_lowercase();
            // 通配匹配主类型(如 image/* 匹配 image/png)
            if p.ends_with("/*") && mime.starts_with(p.trim_end_matches('*')) {
                return true;
            }
            p == mime
        })
    }
}

/// 本地磁盘存储配置
#[derive(Debug, Clone)]
pub struct LocalStorageConfig {
    pub limits: StorageLimits,
    /// 本地存储根目录路径(None = 回退全局上传目录)
    pub base_dir: Option<PathBuf>,
}

/// S3 协议存储配置(s3/rustfs 共用)
#[derive(Debug, Clone)]
pub struct S3StorageConfig {
    pub limits: StorageLimits,
    /// S3 存储桶名称
    pub bucket: String,
    /// S3 服务端点URL(如 http://127.0.0.1:9000)
    pub endpoint_url: String,
    /// S3 区域
    pub region: String,
    pub access_key: String,
    pub secret_key: String,
}

/// 存储配置(工厂产物; 类型决定运行时行为)
#[derive(Debug, Clone)]
pub enum StorageConfig {
    Local(LocalStorageConfig),
    S3(S3StorageConfig),
}

impl StorageConfig {
    /// 实际生效的存储类型
    pub fn storage_type(&self) -> StorageType {
        match self {
            Self::Local(_) => StorageType::Local,
            Self::S3(_) => StorageType::S3,
        }
    }

    pub fn limits(&self) -> &StorageLimits {
        match self {
            Self::Local(c) => &c.limits,
            Self::S3(c) => &c.limits,
        }
    }

    /// 按动态配置装配(对应 Python StorageConfigFactory.create)
    ///
    /// :param fs: file_system 动态配置组
    /// :param fallback_base_dir: local 未配置目录时的回退根目录(全局上传目录)
    pub fn from_settings(fs: &FileSystemSettings, fallback_base_dir: PathBuf) -> Result<Self, AppError> {
        let limits = StorageLimits {
            max_size: fs.max_size,
            allowed_extensions: fs.allowed_extensions.clone(),
        };
        match StorageType::parse(&fs.storage_type).map_err(|e| AppError::business(e.msg))? {
            StorageType::Local => Ok(Self::Local(LocalStorageConfig {
                limits,
                base_dir: Some(fallback_base_dir),
            })),
            // rustfs 与 s3 协议完全兼容, 配置与实现共用(file_content 仅记录 LOCAL/S3 来源)
            StorageType::S3 | StorageType::Rustfs => Ok(Self::S3(S3StorageConfig {
                limits,
                bucket: fs.bucket.clone(),
                endpoint_url: fs.endpoint_url.clone(),
                region: if fs.region.is_empty() { "us-east-1".to_string() } else { fs.region.clone() },
                access_key: fs.access_key.clone(),
                secret_key: fs.secret_key.clone(),
            })),
        }
    }
}
