//! MinerU HTTP 客户端: 远程 mineru.net API v4(批量) 与本地 docker mineru-api 双实现
//! (对齐 Python utils/file_parase/mineru/client.py)。
//!
//! - RemoteMineruClient: `POST /file-urls/batch` 申请预签名上传链接 → PUT 上传
//!   (系统自动建解析任务) → 轮询 `GET /extract-results/batch/{batch_id}` →
//!   下载结果 zip。支持一次批量提交多个文件(单批上限 200)。
//! - LocalMineruClient: `POST {local_endpoint}` multipart 上传, 同步返回结果
//!   zip 流(2.x 契约, 端点可配置以适配其他版本)。
//!
//! 两者统一暴露 `parse` / `parse_batch` 接口(与 Python BaseMinerUClient 一致)。

use std::time::Duration;

use common::config::MinerUSection;
use common::utils::error::AppError;
use serde_json::{json, Value};

/// 远程单批文件数上限(官方限制 200)
const MAX_BATCH_FILES: usize = 200;

// ==================== 统一客户端 ====================

/// 远程/本地统一客户端(对齐 Python build_client 的返回)
pub enum MineruClient {
    Remote(RemoteMineruClient),
    Local(LocalMineruClient),
}

impl MineruClient {
    /// 解析单个文件, 返回结果 zip 字节流
    pub async fn parse(&self, filename: &str, bytes: &[u8]) -> Result<Vec<u8>, AppError> {
        let mut zips = self
            .parse_batch(&[(filename.to_string(), bytes.to_vec())])
            .await?;
        zips.pop().ok_or_else(|| AppError::business("MinerU 返回结果为空"))
    }

    /// 批量解析, 返回与 files 等序的结果 zip 字节列表
    pub async fn parse_batch(&self, files: &[(String, Vec<u8>)]) -> Result<Vec<Vec<u8>>, AppError> {
        match self {
            MineruClient::Remote(c) => c.parse_batch(files).await,
            MineruClient::Local(c) => c.parse_batch(files).await,
        }
    }
}

/// 按配置构建客户端: mode=local 用本地服务, 其余(默认 remote)用远程 API
pub fn build_client(cfg: &MinerUSection) -> Result<MineruClient, AppError> {
    if cfg.mode == "local" {
        tracing::info!("MinerU 使用本地部署: {}{}", cfg.local_base_url, cfg.local_endpoint);
        Ok(MineruClient::Local(LocalMineruClient::new(cfg)))
    } else {
        tracing::info!("MinerU 使用远程 API: {}", cfg.remote_base_url);
        Ok(MineruClient::Remote(RemoteMineruClient::new(cfg)?))
    }
}

// ==================== 远程客户端 ====================

/// mineru.net 远程 API v4 客户端(默认)
///
/// 鉴权: `Authorization: Bearer <token>`。文件上传走预签名 PUT 链接
/// (24h 有效, 上传时不设 Content-Type, 上传完成系统自动提交解析任务)。
pub struct RemoteMineruClient {
    base_url: String,
    token: String,
    http: reqwest::Client,
    cfg: MinerUSection,
}

impl RemoteMineruClient {
    pub fn new(cfg: &MinerUSection) -> Result<Self, AppError> {
        if cfg.token.is_empty() {
            return Err(AppError::business("MinerU 远程模式缺少 token, 请配置 mineru.token"));
        }
        let http = reqwest::Client::builder()
            .timeout(Duration::from_secs_f64(cfg.timeout))
            .build()
            .map_err(|e| AppError::internal(format!("HTTP 客户端构建失败: {e}")))?;
        Ok(Self {
            base_url: cfg.remote_base_url.trim_end_matches('/').to_string(),
            token: cfg.token.clone(),
            http,
            cfg: cfg.clone(),
        })
    }

    /// 批量解析: 按 200 个/批分片提交, 汇总返回等序 zip 列表
    pub async fn parse_batch(&self, files: &[(String, Vec<u8>)]) -> Result<Vec<Vec<u8>>, AppError> {
        let mut results = Vec::with_capacity(files.len());
        for batch in files.chunks(MAX_BATCH_FILES) {
            results.extend(self.parse_one_batch(batch).await?);
        }
        Ok(results)
    }

    /// 单批流程: 申请链接 → 上传 → 轮询 → 下载 zip
    async fn parse_one_batch(&self, files: &[(String, Vec<u8>)]) -> Result<Vec<Vec<u8>>, AppError> {
        // 1. 申请批量上传链接(data_id 记录原始序号, 用于结果对位)
        let payload = json!({
            "enable_formula": self.cfg.enable_formula,
            "enable_table": self.cfg.enable_table,
            "model_version": self.cfg.model_version,
            "language": self.cfg.language,
            "is_ocr": self.cfg.is_ocr,
            "files": files
                .iter()
                .enumerate()
                .map(|(idx, (name, _))| {
                    json!({"name": name, "data_id": idx.to_string(), "is_ocr": self.cfg.is_ocr})
                })
                .collect::<Vec<_>>(),
        });
        let data = self
            .request_data("POST", &format!("{}/file-urls/batch", self.base_url), Some(&payload))
            .await?;
        let batch_id = data
            .get("batch_id")
            .and_then(Value::as_str)
            .filter(|s| !s.is_empty())
            .ok_or_else(|| AppError::business("MinerU 返回上传链接异常: 缺少 batch_id"))?
            .to_string();
        let urls: Vec<String> = data
            .get("file_urls")
            .and_then(Value::as_array)
            .map(|a| a.iter().filter_map(|v| v.as_str().map(str::to_string)).collect())
            .unwrap_or_default();
        if urls.len() != files.len() {
            return Err(AppError::business(format!(
                "MinerU 返回上传链接数量异常: 期望 {} 实际 {}",
                files.len(),
                urls.len()
            )));
        }

        // 2. 上传文件到预签名链接(不设 Content-Type, 由服务端推断)
        for ((name, bytes), url) in files.iter().zip(urls.iter()) {
            let resp = self.http.put(url).body(bytes.clone()).send().await;
            let resp = match resp {
                Ok(r) => r,
                Err(e) => {
                    return Err(AppError::business(format!("MinerU 文件上传失败({name}): {e}")))
                }
            };
            if !resp.status().is_success() {
                return Err(AppError::business(format!(
                    "MinerU 文件上传失败({} {name}): {}",
                    resp.status().as_u16(),
                    resp.text().await.unwrap_or_default()
                )));
            }
        }

        // 3. 轮询批量结果
        let extract_result = self.wait_batch(&batch_id, files.len()).await?;

        // 4. 下载结果 zip(按 data_id 还原输入顺序)
        let mut zips = Vec::with_capacity(files.len());
        for (idx, (name, _)) in files.iter().enumerate() {
            let item = extract_result
                .iter()
                .find(|r| r.get("data_id").and_then(Value::as_str) == Some(idx.to_string().as_str()));
            let Some(item) = item else {
                return Err(AppError::business(format!("MinerU 解析结果缺失: {name}")));
            };
            if item.get("state").and_then(Value::as_str) != Some("done") {
                let err = item.get("err_msg").and_then(Value::as_str).unwrap_or("结果缺失");
                return Err(AppError::business(format!("MinerU 解析失败({name}): {err}")));
            }
            let zip_url = item
                .get("full_zip_url")
                .and_then(Value::as_str)
                .filter(|s| !s.is_empty())
                .ok_or_else(|| AppError::business(format!("MinerU 结果缺少 full_zip_url: {name}")))?;
            zips.push(self.download(zip_url).await?);
        }
        Ok(zips)
    }

    /// 轮询批量解析结果直到全部完成/失败/超时, 返回 extract_result 列表
    async fn wait_batch(&self, batch_id: &str, n: usize) -> Result<Vec<Value>, AppError> {
        let url = format!("{}/extract-results/batch/{batch_id}", self.base_url);
        let deadline = tokio::time::Instant::now() + Duration::from_secs_f64(self.cfg.poll_timeout);
        loop {
            let data = self.request_data("GET", &url, None).await?;
            let results: Vec<Value> = data
                .get("extract_result")
                .and_then(Value::as_array)
                .cloned()
                .unwrap_or_default();
            let states: Vec<&str> = results
                .iter()
                .map(|r| r.get("state").and_then(Value::as_str).unwrap_or(""))
                .collect();
            if states.contains(&"failed") {
                let errs: Vec<String> = results
                    .iter()
                    .filter(|r| r.get("state").and_then(Value::as_str) == Some("failed"))
                    .filter_map(|r| r.get("err_msg").and_then(Value::as_str).map(str::to_string))
                    .collect();
                return Err(AppError::business(format!("MinerU 解析失败: {errs:?}")));
            }
            if results.len() == n && states.iter().all(|s| *s == "done") {
                return Ok(results);
            }
            if tokio::time::Instant::now() >= deadline {
                return Err(AppError::business(format!(
                    "MinerU 解析超时({}s), batch_id={batch_id}",
                    self.cfg.poll_timeout
                )));
            }
            tracing::debug!("MinerU 批量任务 {batch_id} 进行中: {states:?}");
            tokio::time::sleep(Duration::from_secs_f64(self.cfg.poll_interval)).await;
        }
    }

    /// 发送带鉴权的 JSON 请求并校验响应, 返回 data 节
    async fn request_data(
        &self,
        method: &str,
        url: &str,
        body: Option<&Value>,
    ) -> Result<Value, AppError> {
        let method = reqwest::Method::from_bytes(method.as_bytes())
            .map_err(|e| AppError::internal(format!("HTTP 方法非法: {e}")))?;
        let mut req = self.http.request(method, url).bearer_auth(&self.token);
        if let Some(json) = body {
            req = req.json(json);
        }
        let resp = req
            .send()
            .await
            .map_err(|e| AppError::business(format!("MinerU 接口请求失败({url}): {e}")))?;
        let status = resp.status();
        let text = resp.text().await.unwrap_or_default();
        if !status.is_success() {
            let short: String = text.chars().take(500).collect();
            return Err(AppError::business(format!(
                "MinerU 接口请求失败({} {url}): {short}",
                status.as_u16()
            )));
        }
        let body: Value = serde_json::from_str(&text)
            .map_err(|e| AppError::business(format!("MinerU 接口响应解析失败({url}): {e}")))?;
        // code 为 0(数值/字符串) 视为成功, 其余报 msg
        let code_ok = body.get("code").map(|c| c.as_i64() == Some(0) || c.as_str() == Some("0"))
            .unwrap_or(false);
        if !code_ok {
            let msg = body.get("msg").and_then(Value::as_str).unwrap_or("未知错误");
            return Err(AppError::business(format!("MinerU 接口返回错误({url}): {msg}")));
        }
        Ok(body.get("data").cloned().unwrap_or(Value::Null))
    }

    /// 下载结果 zip(预签名链接, 无需鉴权头)
    async fn download(&self, url: &str) -> Result<Vec<u8>, AppError> {
        let resp = self
            .http
            .get(url)
            .send()
            .await
            .map_err(|e| AppError::business(format!("MinerU 结果下载失败({url}): {e}")))?;
        let status = resp.status();
        if !status.is_success() {
            return Err(AppError::business(format!(
                "MinerU 结果下载失败({} {url})",
                status.as_u16()
            )));
        }
        let bytes = resp
            .bytes()
            .await
            .map_err(|e| AppError::business(format!("MinerU 结果读取失败({url}): {e}")))?;
        Ok(bytes.to_vec())
    }
}

// ==================== 本地客户端 ====================

/// 本地 docker mineru-api 客户端(2.x 契约, 端点可配置)
///
/// `POST {local_base_url}{local_endpoint}` multipart 上传, 同步返回 zip 流。
/// 请求参数按 2.x web_api: is_ocr/lang/backend/return_content_list 等。
pub struct LocalMineruClient {
    url: String,
    http: reqwest::Client,
    cfg: MinerUSection,
}

impl LocalMineruClient {
    pub fn new(cfg: &MinerUSection) -> Self {
        let url = format!("{}{}", cfg.local_base_url.trim_end_matches('/'), cfg.local_endpoint);
        let http = reqwest::Client::builder()
            .timeout(Duration::from_secs_f64(cfg.timeout))
            .build()
            .expect("HTTP 客户端构建失败");
        Self { url, http, cfg: cfg.clone() }
    }

    /// 本地服务无批量端点, 逐文件顺序解析
    pub async fn parse_batch(&self, files: &[(String, Vec<u8>)]) -> Result<Vec<Vec<u8>>, AppError> {
        let mut results = Vec::with_capacity(files.len());
        for (name, bytes) in files {
            results.push(self.parse_one(name, bytes).await?);
        }
        Ok(results)
    }

    async fn parse_one(&self, name: &str, bytes: &[u8]) -> Result<Vec<u8>, AppError> {
        tracing::info!("MinerU 本地解析: {name} -> {}", self.url);
        let form = reqwest::multipart::Form::new()
            .part(
                "file",
                reqwest::multipart::Part::bytes(bytes.to_vec()).file_name(name.to_string()),
            )
            .text("is_ocr", self.cfg.is_ocr.to_string())
            .text("lang", self.cfg.language.clone())
            .text("backend", self.cfg.model_version.clone())
            .text("return_content_list", "true")
            .text("return_middle_json", "false")
            .text("return_figures", "false");
        let resp = self
            .http
            .post(&self.url)
            .multipart(form)
            .send()
            .await
            .map_err(|e| AppError::business(format!("MinerU 本地解析请求失败({name}): {e}")))?;
        let status = resp.status();
        let content = resp
            .bytes()
            .await
            .map_err(|e| AppError::business(format!("MinerU 本地结果读取失败({name}): {e}")))?;
        if !status.is_success() {
            let short: String = String::from_utf8_lossy(&content).chars().take(500).collect();
            return Err(AppError::business(format!(
                "MinerU 本地解析失败({} {name}): {short}",
                status.as_u16()
            )));
        }
        if !content.starts_with(b"PK") {
            // 非 zip 响应: 多为参数/版本不匹配的错误 JSON
            let short: String = String::from_utf8_lossy(&content).chars().take(500).collect();
            return Err(AppError::business(format!("MinerU 本地服务返回非 zip 结果: {short}")));
        }
        Ok(content.to_vec())
    }
}
