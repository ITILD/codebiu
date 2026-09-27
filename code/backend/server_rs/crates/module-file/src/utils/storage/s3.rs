//! S3 协议对象存储实现(对齐 Python storage_s3.py; s3/rustfs 共用)
//!
//! 物理键相对 bucket 解析: bucket/key
//! 分片上传走 S3 multipart 协议, 完成时按内容哈希 copy 到归位键并清理临时键。

use aws_sdk_s3::config::{BehaviorVersion, Credentials, Region};
use aws_sdk_s3::presigning::PresigningConfig;
use aws_sdk_s3::primitives::ByteStream;
use aws_sdk_s3::types::{BucketLocationConstraint, CompletedMultipartUpload, CompletedPart, CorsRule};
use aws_sdk_s3::types::{CreateBucketConfiguration, CorsConfiguration};
use aws_sdk_s3::Client;
use bytes::Bytes;
use futures::future::BoxFuture;
use futures::StreamExt;
use sha2::{Digest, Sha256};

use common::utils::error::AppError;

use crate::do_::storage::S3StorageConfig;
use crate::utils::storage::{strip_etag_quotes, CompleteResult, PartInfo, Storage};

/// S3 SDK 错误统一转 500(调用失败属于服务端/存储端故障)
fn sdk_err(e: impl std::fmt::Display) -> AppError {
    AppError::internal(format!("对象存储调用失败: {e}"))
}

pub struct S3Storage {
    client: Client,
    bucket: String,
}

impl S3Storage {
    /// 按动态配置手工构建客户端(不走 aws-config 环境链, 与 Python 显式传参一致)
    pub fn new(config: S3StorageConfig) -> Self {
        let s3_config = aws_sdk_s3::Config::builder()
            .behavior_version(BehaviorVersion::latest())
            .region(Region::new(config.region))
            .credentials_provider(Credentials::new(
                config.access_key,
                config.secret_key,
                None::<String>,
                None::<std::time::SystemTime>,
                "file-storage",
            ))
            .endpoint_url(config.endpoint_url)
            // 自建对象存储(minio/rustfs)普遍为路径风格
            .force_path_style(true)
            .build();
        Self {
            client: Client::from_conf(s3_config),
            bucket: config.bucket,
        }
    }

    /// 完成分片后按内容哈希归位: 目标键已存在则删临时键复用, 否则 copy 后删临时键
    async fn relocate(
        &self,
        key: &str,
        hash: &str,
        size: i64,
    ) -> Result<(String, i64, String), AppError> {
        let ext = std::path::Path::new(key)
            .extension()
            .map(|e| format!(".{}", e.to_string_lossy()))
            .unwrap_or_default();
        let final_key = format!("uploads/{}/{}{}", crate::do_::filesystem::today_key(), hash, ext);
        if self.exists(&final_key).await {
            // 相同内容已存在(内容哈希去重), 直接删除分片临时键
            self.delete(key).await;
        } else {
            self.client
                .copy_object()
                .bucket(&self.bucket)
                .key(&final_key)
                .copy_source(format!("{}/{}", self.bucket, key))
                .send()
                .await
                .map_err(sdk_err)?;
            self.delete(key).await;
        }
        Ok((hash.to_string(), size, final_key))
    }

    /// 流式读取对象内容并计算 SHA-256 与大小
    async fn hash_stream(&self, key: &str) -> Result<(String, i64), AppError> {
        let resp = self
            .client
            .get_object()
            .bucket(&self.bucket)
            .key(key)
            .send()
            .await
            .map_err(sdk_err)?;
        let mut hasher = Sha256::new();
        let mut size: i64 = 0;
        let mut body = resp.body;
        while let Some(chunk) = body.next().await {
            let chunk = chunk.map_err(sdk_err)?;
            hasher.update(&chunk);
            size += chunk.len() as i64;
        }
        Ok((crate::utils::storage::local::hex_encode(&hasher.finalize()), size))
    }
}

#[async_trait::async_trait]
impl Storage for S3Storage {
    fn kind(&self) -> &'static str {
        "s3"
    }

    async fn save(&self, key: &str, data: &[u8]) -> Result<(), AppError> {
        self.client
            .put_object()
            .bucket(&self.bucket)
            .key(key)
            .body(ByteStream::from(Bytes::copy_from_slice(data)))
            .send()
            .await
            .map_err(sdk_err)?;
        Ok(())
    }

    async fn load(&self, key: &str) -> Result<Bytes, AppError> {
        let resp = self
            .client
            .get_object()
            .bucket(&self.bucket)
            .key(key)
            .send()
            .await
            .map_err(sdk_err)?;
        let data = resp.body.collect().await.map_err(sdk_err)?;
        Ok(data.into_bytes())
    }

    fn stream(
        &self,
        key: &str,
        _chunk_size: usize,
    ) -> BoxFuture<
        'static,
        Result<futures::stream::BoxStream<'static, Result<Bytes, std::io::Error>>, AppError>,
    > {
        let client = self.client.clone();
        let bucket = self.bucket.clone();
        let key = key.to_string();
        Box::pin(async move {
            let resp = client
                .get_object()
                .bucket(&bucket)
                .key(&key)
                .send()
                .await
                .map_err(sdk_err)?;
            // ByteStream 未实现 futures Stream: 用固有 try_next 经 unfold 适配(错误转 io::Error)
            let stream = futures::stream::unfold(resp.body, |mut body| async move {
                match body.try_next().await {
                    Ok(Some(chunk)) => Some((Ok(chunk), body)),
                    Ok(None) => None,
                    Err(e) => Some((Err(std::io::Error::other(e.to_string())), body)),
                }
            })
            .boxed();
            Ok(stream)
        })
    }

    async fn delete(&self, key: &str) -> bool {
        self.client
            .delete_object()
            .bucket(&self.bucket)
            .key(key)
            .send()
            .await
            .is_ok()
    }

    async fn exists(&self, key: &str) -> bool {
        self.client
            .head_object()
            .bucket(&self.bucket)
            .key(key)
            .send()
            .await
            .is_ok()
    }

    fn supports_presign(&self) -> bool {
        // S3 协议存储支持预签名直传(数据面不经过服务端)
        true
    }

    async fn create_multipart(&self, key: &str, content_type: &str) -> Result<String, AppError> {
        let resp = self
            .client
            .create_multipart_upload()
            .bucket(&self.bucket)
            .key(key)
            .content_type(content_type)
            .send()
            .await
            .map_err(sdk_err)?;
        resp.upload_id
            .ok_or_else(|| AppError::internal("S3 分片会话创建失败: 未返回 UploadId"))
    }

    async fn upload_part(
        &self,
        key: &str,
        upload_id: &str,
        part_number: i64,
        data: &[u8],
    ) -> Result<PartInfo, AppError> {
        let resp = self
            .client
            .upload_part()
            .bucket(&self.bucket)
            .key(key)
            .upload_id(upload_id)
            .part_number(part_number as i32)
            .body(ByteStream::from(Bytes::copy_from_slice(data)))
            .send()
            .await
            .map_err(sdk_err)?;
        Ok(PartInfo {
            part_number,
            etag: resp.e_tag.map(|t| strip_etag_quotes(&t)).unwrap_or_default(),
            size: data.len() as i64,
        })
    }

    async fn list_parts(&self, key: &str, upload_id: &str) -> Result<Vec<PartInfo>, AppError> {
        let resp = self
            .client
            .list_parts()
            .bucket(&self.bucket)
            .key(key)
            .upload_id(upload_id)
            .send()
            .await
            .map_err(sdk_err)?;
        let mut parts: Vec<PartInfo> = resp
            .parts
            .unwrap_or_default()
            .into_iter()
            .filter_map(|p| {
                Some(PartInfo {
                    part_number: p.part_number? as i64,
                    etag: p.e_tag.map(|t| strip_etag_quotes(&t)).unwrap_or_default(),
                    size: p.size.unwrap_or(0),
                })
            })
            .collect();
        parts.sort_by_key(|p| p.part_number);
        Ok(parts)
    }

    async fn complete_multipart(
        &self,
        key: &str,
        upload_id: &str,
        parts: &[PartInfo],
        expected_hash: Option<&str>,
    ) -> Result<CompleteResult, AppError> {
        // S3 合并分片(以传入顺序组装, part_number 必须升序)
        let mut ordered: Vec<&PartInfo> = parts.iter().collect();
        ordered.sort_by_key(|p| p.part_number);
        let completed: Vec<CompletedPart> = ordered
            .iter()
            .map(|p| CompletedPart::builder().part_number(p.part_number as i32).e_tag(&p.etag).build())
            .collect();
        self.client
            .complete_multipart_upload()
            .bucket(&self.bucket)
            .key(key)
            .upload_id(upload_id)
            .multipart_upload(
                CompletedMultipartUpload::builder().set_parts(Some(completed)).build(),
            )
            .send()
            .await
            .map_err(sdk_err)?;

        // 归位哈希: 直传场景信任前端 SHA-256(签发阶段已校验); 中转场景流式重算
        if let Some(expected) = expected_hash {
            let head = self
                .client
                .head_object()
                .bucket(&self.bucket)
                .key(key)
                .send()
                .await
                .map_err(sdk_err)?;
            let size = head.content_length.unwrap_or(0);
            return self.relocate(key, expected, size).await;
        }
        let (hash, size) = self.hash_stream(key).await?;
        self.relocate(key, &hash, size).await
    }

    async fn abort_multipart(&self, key: &str, upload_id: &str) -> Result<(), AppError> {
        self.client
            .abort_multipart_upload()
            .bucket(&self.bucket)
            .key(key)
            .upload_id(upload_id)
            .send()
            .await
            .map_err(sdk_err)?;
        Ok(())
    }

    async fn presign_put(
        &self,
        key: &str,
        upload_id: Option<&str>,
        part_number: Option<i64>,
        expires: u64,
    ) -> Result<Option<String>, AppError> {
        let presign = PresigningConfig::expires_in(crate::utils::storage::presign_ttl(expires))
            .map_err(sdk_err)?;
        let req = match (upload_id, part_number) {
            // 分片直传: 预签名 upload_part
            (Some(uid), Some(n)) => self
                .client
                .upload_part()
                .bucket(&self.bucket)
                .key(key)
                .upload_id(uid)
                .part_number(n as i32)
                .presigned(presign)
                .await
                .map_err(sdk_err)?,
            // 整文件直传(预留口径, 与 Python 一致)
            _ => self
                .client
                .put_object()
                .bucket(&self.bucket)
                .key(key)
                .presigned(presign)
                .await
                .map_err(sdk_err)?,
        };
        Ok(Some(req.uri().to_string()))
    }

    async fn presign_get(
        &self,
        key: &str,
        expires: u64,
        download_filename: Option<&str>,
    ) -> Result<Option<String>, AppError> {
        let presign = PresigningConfig::expires_in(crate::utils::storage::presign_ttl(expires))
            .map_err(sdk_err)?;
        let mut req = self
            .client
            .get_object()
            .bucket(&self.bucket)
            .key(key);
        if let Some(name) = download_filename {
            // RFC 5987 编码文件名(支持中文等非 ASCII 字符)
            let encoded = percent_encoding::utf8_percent_encode(
                name,
                percent_encoding::NON_ALPHANUMERIC,
            )
            .to_string();
            req = req.response_content_disposition(format!("attachment; filename*=UTF-8''{encoded}"));
        }
        let signed = req.presigned(presign).await.map_err(sdk_err)?;
        Ok(Some(signed.uri().to_string()))
    }

    /// 启动期就绪检查: 建桶(不存在时) + 配置 CORS(浏览器直传需要)
    async fn ensure_ready(&self) -> Result<(), AppError> {
        // 桶已存在则跳过创建
        if self
            .client
            .head_bucket()
            .bucket(&self.bucket)
            .send()
            .await
            .is_err()
        {
            let mut create = self.client.create_bucket().bucket(&self.bucket);
            // us-east-1 不允许携带 LocationConstraint
            if self
                .client
                .config()
                .region()
                .map(|r| r.to_string() != "us-east-1")
                .unwrap_or(false)
            {
                let region = self
                    .client
                    .config()
                    .region()
                    .map(|r| r.to_string())
                    .unwrap_or_else(|| "us-east-1".to_string());
                create = create.create_bucket_configuration(
                    CreateBucketConfiguration::builder()
                        .location_constraint(BucketLocationConstraint::from(region.as_str()))
                        .build(),
                );
            }
            create.send().await.map_err(sdk_err)?;
        }
        // CORS: 允许浏览器直接 PUT/GET/HEAD 并读取 ETag(分片对账必需)
        let rule = CorsRule::builder()
            .allowed_methods("GET")
            .allowed_methods("PUT")
            .allowed_methods("HEAD")
            .allowed_origins("*")
            .allowed_headers("*")
            .expose_headers("ETag")
            .build()
            .map_err(sdk_err)?;
        let cors = CorsConfiguration::builder()
            .cors_rules(rule)
            .build()
            .map_err(sdk_err)?;
        self.client
            .put_bucket_cors()
            .bucket(&self.bucket)
            .cors_configuration(cors)
            .send()
            .await
            .map_err(sdk_err)?;
        Ok(())
    }
}
