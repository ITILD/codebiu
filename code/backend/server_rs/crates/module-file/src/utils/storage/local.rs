//! 本地磁盘存储实现(对齐 Python storage_local.py)
//!
//! 物理键相对 base_dir 解析: base_dir/key
//! 分片上传: 分片暂存 base_dir/.multipart/{upload_id}/{n}, 完成时合并并按内容哈希归位

use std::path::{Path, PathBuf};

use async_trait::async_trait;
use bytes::Bytes;
use futures::future::BoxFuture;
use futures::StreamExt;
use sha2::{Digest, Sha256};
use tokio::io::AsyncReadExt;

use common::utils::error::AppError;

use crate::do_::storage::LocalStorageConfig;
use crate::utils::storage::{CompleteResult, PartInfo, Storage};

pub struct LocalStorage {
    base_dir: PathBuf,
}

impl LocalStorage {
    /// 构建并确保根目录存在
    pub fn new(config: LocalStorageConfig) -> Self {
        let base_dir = config
            .base_dir
            .unwrap_or_else(|| PathBuf::from("temp_source/upload"));
        std::fs::create_dir_all(&base_dir).ok();
        Self { base_dir }
    }

    /// 物理键 → 本地路径
    fn resolve(&self, key: &str) -> PathBuf {
        self.base_dir.join(key)
    }

    /// 分片会话暂存目录(仅允许安全字符, 防路径穿越)
    fn multipart_dir(&self, upload_id: &str) -> Result<PathBuf, AppError> {
        if upload_id.is_empty() || !upload_id.chars().all(|c| c.is_ascii_alphanumeric()) {
            return Err(AppError::business("非法的分片上传会话ID"));
        }
        Ok(self.base_dir.join(".multipart").join(upload_id))
    }
}

#[async_trait]
impl Storage for LocalStorage {
    fn kind(&self) -> &'static str {
        "local"
    }

    async fn save(&self, key: &str, data: &[u8]) -> Result<(), AppError> {
        let path = self.resolve(key);
        if let Some(parent) = path.parent() {
            tokio::fs::create_dir_all(parent).await?;
        }
        tokio::fs::write(&path, data).await?;
        Ok(())
    }

    async fn load(&self, key: &str) -> Result<Bytes, AppError> {
        let data = tokio::fs::read(self.resolve(key)).await?;
        Ok(Bytes::from(data))
    }

    fn stream(
        &self,
        key: &str,
        chunk_size: usize,
    ) -> BoxFuture<
        'static,
        Result<futures::stream::BoxStream<'static, Result<Bytes, std::io::Error>>, AppError>,
    > {
        let path = self.resolve(key);
        Box::pin(async move {
            let file = tokio::fs::File::open(&path)
                .await
                .map_err(|e| AppError::not_found(format!("打开物理文件失败: {e}")))?;
            let chunk_size = chunk_size.max(1);
            let stream = futures::stream::unfold((file, chunk_size), |(mut f, size)| async move {
                let mut buf = vec![0u8; size];
                match f.read(&mut buf).await {
                    Ok(0) => None,
                    Ok(n) => Some((Ok(Bytes::from(buf[..n].to_vec())), (f, size))),
                    Err(e) => Some((Err(e), (f, size))),
                }
            });
            Ok(stream.boxed())
        })
    }

    async fn delete(&self, key: &str) -> bool {
        matches!(tokio::fs::remove_file(self.resolve(key)).await, Ok(()))
    }

    async fn exists(&self, key: &str) -> bool {
        Path::new(&self.base_dir).join(key).exists()
    }

    fn supports_presign(&self) -> bool {
        // 本地磁盘不支持浏览器直传(前端走服务端中转)
        false
    }

    async fn create_multipart(&self, _key: &str, _content_type: &str) -> Result<String, AppError> {
        let upload_id = uuid::Uuid::new_v4().simple().to_string();
        tokio::fs::create_dir_all(self.multipart_dir(&upload_id)?).await?;
        Ok(upload_id)
    }

    async fn upload_part(
        &self,
        _key: &str,
        upload_id: &str,
        part_number: i64,
        data: &[u8],
    ) -> Result<PartInfo, AppError> {
        let part_file = self.multipart_dir(upload_id)?.join(part_number.to_string());
        tokio::fs::write(&part_file, data).await?;
        // 本地存储 ETag 即分片大小(与 Python str(len(data)) 一致)
        Ok(PartInfo {
            part_number,
            etag: data.len().to_string(),
            size: data.len() as i64,
        })
    }

    async fn list_parts(&self, _key: &str, upload_id: &str) -> Result<Vec<PartInfo>, AppError> {
        let session_dir = self.multipart_dir(upload_id)?;
        if !session_dir.exists() {
            return Ok(Vec::new());
        }
        let mut entries: Vec<(i64, u64)> = Vec::new();
        let mut rd = tokio::fs::read_dir(&session_dir).await?;
        while let Some(entry) = rd.next_entry().await? {
            let name = entry.file_name().to_string_lossy().to_string();
            if let Ok(n) = name.parse::<i64>() {
                let size = entry.metadata().await?.len();
                entries.push((n, size));
            }
        }
        entries.sort_by_key(|(n, _)| *n);
        Ok(entries
            .into_iter()
            .map(|(n, size)| PartInfo {
                part_number: n,
                // 本地 ETag 即分片大小
                etag: size.to_string(),
                size: size as i64,
            })
            .collect())
    }

    async fn complete_multipart(
        &self,
        key: &str,
        upload_id: &str,
        parts: &[PartInfo],
        _expected_hash: Option<&str>,
    ) -> Result<CompleteResult, AppError> {
        // 本地存储数据面本就在服务端, 直接以合并时算出的真实哈希为准
        let session_dir = self.multipart_dir(upload_id)?;
        if !session_dir.exists() {
            return Err(AppError::business(format!("分片上传会话不存在: {upload_id}")));
        }
        let merged = session_dir.join("merged");
        let mut hasher = Sha256::new();
        let mut total: i64 = 0;
        let mut ordered: Vec<&PartInfo> = parts.iter().collect();
        ordered.sort_by_key(|p| p.part_number);
        {
            let mut out = tokio::fs::File::create(&merged).await?;
            for p in ordered {
                let part_file = session_dir.join(p.part_number.to_string());
                if !part_file.exists() {
                    return Err(AppError::business(format!(
                        "分片缺失: {}",
                        p.part_number
                    )));
                }
                let mut f = tokio::fs::File::open(&part_file).await?;
                let mut buf = vec![0u8; 1024 * 1024];
                loop {
                    let n = f.read(&mut buf).await?;
                    if n == 0 {
                        break;
                    }
                    hasher.update(&buf[..n]);
                    total += n as i64;
                    tokio::io::AsyncWriteExt::write_all(&mut out, &buf[..n]).await?;
                }
            }
        }
        // 按内容哈希生成最终物理键(与直传 uploads/{date}/{hash}{ext} 规则一致)
        let hash = hex_encode(&hasher.finalize());
        let ext = std::path::Path::new(key)
            .extension()
            .map(|e| format!(".{}", e.to_string_lossy()))
            .unwrap_or_default();
        let final_key = format!("uploads/{}/{}{}", crate::do_::filesystem::today_key(), hash, ext);
        let final_path = self.base_dir.join(&final_key);
        tokio::fs::create_dir_all(final_path.parent().expect("最终键必有父目录")).await?;
        if final_path.exists() {
            // 相同内容已存在, 复用物理文件(内容哈希去重)
            tokio::fs::remove_file(&merged).await.ok();
        } else {
            tokio::fs::rename(&merged, &final_path).await?;
        }
        tokio::fs::remove_dir_all(&session_dir).await.ok();
        Ok((hash, total, final_key))
    }

    async fn abort_multipart(&self, _key: &str, upload_id: &str) -> Result<(), AppError> {
        let dir = self.multipart_dir(upload_id)?;
        tokio::fs::remove_dir_all(&dir).await.ok();
        Ok(())
    }

    async fn presign_put(
        &self,
        _key: &str,
        _upload_id: Option<&str>,
        _part_number: Option<i64>,
        _expires: u64,
    ) -> Result<Option<String>, AppError> {
        // 本地磁盘不支持浏览器直传(返回None, 前端走服务端中转)
        Ok(None)
    }

    async fn presign_get(
        &self,
        _key: &str,
        _expires: u64,
        _download_filename: Option<&str>,
    ) -> Result<Option<String>, AppError> {
        // 本地磁盘不支持浏览器直连下载(返回None, 前端走服务端流式代理)
        Ok(None)
    }
}

/// 字节数组 → 小写 hex 字符串
pub(crate) fn hex_encode(data: &[u8]) -> String {
    data.iter().map(|b| format!("{b:02x}")).collect()
}
