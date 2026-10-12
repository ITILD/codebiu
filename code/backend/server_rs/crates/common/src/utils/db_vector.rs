//! Milvus 向量库客户端(REST v2 协议)
//!
//! 对齐 Python 侧 pymilvus AsyncMilvusClient 的使用面, 但不引入 gRPC SDK
//! (tonic 依赖重), 改走 Milvus 2.4+ 的 RESTful v2 端点。两个后端共用同一
//! 集合 projectdocumentchunk(schema/BM25 Function/HNSW 索引完全一致),
//! 数据互通, 可随时互换服务进程。
//!
//! 配置来源: 动态配置组 db_vector(sys_config 表), 启动时读取一次装配
//! (连接级配置, 变更需重启, 与 Python 侧 restart_required 语义一致)。

use std::sync::Arc;

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

use crate::config::dynamic::schemas::DBVectorSettings;

/// 分块行(对齐 Python ProjectDocumentChunk 模型字段)
///
/// sparse 字段无需写入: 由 Milvus 服务端 BM25 Function(content → sparse)自动生成。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChunkRow {
    pub id: String,
    #[serde(default)]
    pub sort: i64,
    pub document_id: String,
    pub project_id: String,
    pub content: String,
    #[serde(default)]
    pub source: String,
    #[serde(default)]
    pub content_types: Vec<String>,
    #[serde(default)]
    pub position: Value,
    #[serde(default)]
    pub metadata: Value,
    pub embedding: Vec<f64>,
}

/// 检索命中(实体字段 + 得分; score 为 RRF 融合得分或 rerank 相关性分)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChunkHit {
    #[serde(default)]
    pub id: String,
    #[serde(default)]
    pub sort: i64,
    #[serde(default)]
    pub document_id: String,
    #[serde(default)]
    pub project_id: String,
    #[serde(default)]
    pub content: String,
    #[serde(default)]
    pub source: String,
    #[serde(default)]
    pub content_types: Vec<String>,
    #[serde(default)]
    pub position: Value,
    #[serde(default)]
    pub metadata: Value,
    #[serde(default)]
    pub score: f64,
}

/// 分块集合名(与 Python ProjectDocumentChunk.__name__.lower() 一致)
pub const CHUNK_COLLECTION: &str = "projectdocumentchunk";
/// 默认向量维度(与 Python 侧 json_schema_extra vector_dim 一致)
pub const DEFAULT_EMBEDDING_DIM: i64 = 1024;
/// 单批写入行数(对齐 Python revectorize 的手动分批上限)
const BATCH_SIZE: usize = 200;

/// Milvus REST v2 客户端(轻量不可变, 惰性使用; 无内部连接态)
pub struct MilvusClient {
    /// 基地址(如 http://47.94.107.62:20005)
    base: String,
    /// 数据库名
    db: String,
    /// Bearer 凭证(user:password; 未配置认证时为 None)
    auth: Option<String>,
    http: reqwest::Client,
}

impl MilvusClient {
    /// 按动态配置构造客户端(不发起网络请求, 连接失败延迟到首次调用暴露)
    pub fn new(cfg: &DBVectorSettings) -> Self {
        // host 形如 "http://47.94.107.62"(含 scheme), port 独立字段
        let host = cfg.host.trim_end_matches('/');
        let base = format!("{host}:{}", cfg.port);
        // 认证口径对齐 Python: token 优先, 其次 user+password 成对出现才携带
        let auth = if !cfg.user.is_empty() {
            match &cfg.password {
                Some(p) if !p.is_empty() => Some(format!("{}:{}", cfg.user, p)),
                // 部署未开启认证时携带 user 亦可被忽略, 但为稳妥仅在有密码时携带
                _ => None,
            }
        } else {
            None
        };
        let http = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(60))
            .build()
            .expect("Milvus HTTP 客户端构建失败");
        Self {
            base,
            db: if cfg.database.is_empty() {
                "default".to_string()
            } else {
                cfg.database.clone()
            },
            auth,
            http,
        }
    }

    /// 统一请求入口: POST {base}/v2/vectordb/{path}, code != 0 视为业务错误
    async fn call(&self, path: &str, mut body: Value) -> Result<Value, String> {
        // Milvus REST v2 要求 dbName 内嵌请求体
        if let Some(obj) = body.as_object_mut() {
            obj.insert("dbName".into(), json!(self.db));
        }
        let url = format!("{}/v2/vectordb/{}", self.base, path);
        let mut req = self
            .http
            .post(&url)
            .timeout(std::time::Duration::from_secs(120))
            .header("Content-Type", "application/json");
        if let Some(token) = &self.auth {
            req = req.header("Authorization", format!("Bearer {token}"));
        }
        let resp = req
            .json(&body)
            .send()
            .await
            .map_err(|e| format!("Milvus 请求失败({path}): {e}"))?;
        let status = resp.status();
        let payload: Value = resp
            .json()
            .await
            .map_err(|e| format!("Milvus 响应解析失败({path}): {e}"))?;
        if !status.is_success() {
            return Err(format!(
                "Milvus HTTP {status}({path}): {}",
                payload.get("message").and_then(|m| m.as_str()).unwrap_or("")
            ));
        }
        let code = payload.get("code").and_then(|c| c.as_i64()).unwrap_or(-1);
        if code != 0 {
            return Err(format!(
                "Milvus 错误({path}): {}",
                payload.get("message").and_then(|m| m.as_str()).unwrap_or("未知")
            ));
        }
        Ok(payload)
    }

    // ==================== 集合管理 ====================

    /// 列出全部集合名(同时用作连接健康检查)
    pub async fn list_collections(&self) -> Result<Vec<String>, String> {
        let resp = self.call("collections/list", json!({})).await?;
        let names = resp
            .get("data")
            .and_then(|d| d.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str().map(String::from))
                    .collect()
            })
            .unwrap_or_default();
        Ok(names)
    }

    /// 集合是否存在
    ///
    /// 注: 不同 Milvus 版本 REST v2 的响应字段不同(旧版 hasExists / 新版 has), 兼容读取。
    pub async fn has_collection(&self, name: &str) -> Result<bool, String> {
        let resp = self
            .call("collections/has", json!({ "collectionName": name }))
            .await?;
        Ok(resp
            .get("data")
            .and_then(|d| d.get("hasExists").or_else(|| d.get("has")))
            .and_then(|v| v.as_bool())
            .unwrap_or(false))
    }

    /// 集合元数据(describe)
    pub async fn describe_collection(&self, name: &str) -> Result<Value, String> {
        let resp = self
            .call("collections/describe", json!({ "collectionName": name }))
            .await?;
        Ok(resp.get("data").cloned().unwrap_or(Value::Null))
    }

    /// 读取集合中指定向量字段的维度(集合/字段不存在返回 None)
    pub async fn collection_dim(&self, name: &str, field: &str) -> Option<i64> {
        let schema = self.describe_collection(name).await.ok()?;
        let dim = schema
            .get("fields")?
            .as_array()?
            .iter()
            .find(|f| f.get("name").and_then(|n| n.as_str()) == Some(field))?
            .get("params")?
            .as_array()?
            .iter()
            .find(|p| p.get("key").and_then(|k| k.as_str()) == Some("dim"))?
            .get("value")?
            .as_str()?
            .parse()
            .ok()?;
        Some(dim)
    }

    /// 集合行数统计(get_stats)
    pub async fn collection_count(&self, name: &str) -> Result<i64, String> {
        let resp = self
            .call("collections/get_stats", json!({ "collectionName": name }))
            .await?;
        let count = resp
            .get("data")
            .and_then(|d| d.get("rowCount"))
            .and_then(|v| v.as_i64())
            .unwrap_or(0);
        Ok(count)
    }

    /// 创建分块集合(schema 对齐 Python create_table: BM25 Function + HNSW COSINE + 稀疏倒排)
    pub async fn create_chunk_collection(&self, dim: i64) -> Result<(), String> {
        let body = json!({
            "collectionName": CHUNK_COLLECTION,
            "schema": {
                "autoId": false,
                "enableDynamicField": false,
                "fields": [
                    { "fieldName": "id", "dataType": "VarChar", "isPrimary": true,
                      "elementTypeParams": { "max_length": "255" } },
                    { "fieldName": "sort", "dataType": "Int64" },
                    { "fieldName": "document_id", "dataType": "VarChar",
                      "elementTypeParams": { "max_length": "255" } },
                    { "fieldName": "project_id", "dataType": "VarChar",
                      "elementTypeParams": { "max_length": "255" } },
                    { "fieldName": "content", "dataType": "VarChar",
                      "elementTypeParams": {
                        "max_length": "8192",
                        "enable_analyzer": "true",
                        "analyzer_params": "{\"tokenizer\": \"icu\"}"
                      } },
                    { "fieldName": "source", "dataType": "VarChar",
                      "elementTypeParams": { "max_length": "255" } },
                    { "fieldName": "content_types", "dataType": "Array",
                      "elementType": "VarChar",
                      "elementTypeParams": { "max_length": "255", "max_capacity": "64" } },
                    { "fieldName": "position", "dataType": "JSON" },
                    { "fieldName": "metadata", "dataType": "JSON" },
                    { "fieldName": "embedding", "dataType": "FloatVector",
                      "elementTypeParams": { "dim": dim.to_string() } },
                    { "fieldName": "sparse", "dataType": "SparseFloatVector",
                      "isFunctionOutput": true }
                ],
                "functions": [
                    { "name": "bm25_content_to_sparse", "type": "BM25",
                      "inputFieldNames": ["content"], "outputFieldNames": ["sparse"] }
                ]
            },
            "indexParams": [
                { "fieldName": "embedding", "indexName": "projectdocumentchunk_embedding_index",
                  "metricType": "COSINE", "indexType": "HNSW",
                  "params": { "M": "64", "efConstruction": "100" } },
                { "fieldName": "sparse", "indexName": "sparse",
                  "metricType": "BM25", "indexType": "SPARSE_INVERTED_INDEX" }
            ]
        });
        self.call("collections/create", body).await?;
        // 建表即加载(对齐 Python create_table 末尾 load_collection)
        self.load_collection(CHUNK_COLLECTION).await
    }

    /// 加载集合到内存
    pub async fn load_collection(&self, name: &str) -> Result<(), String> {
        self.call("collections/load", json!({ "collectionName": name }))
            .await
            .map(|_| ())
    }

    /// 删除集合(维度变更重建用)
    pub async fn drop_collection(&self, name: &str) -> Result<(), String> {
        self.call("collections/drop", json!({ "collectionName": name }))
            .await
            .map(|_| ())
    }

    // ==================== 数据读写 ====================

    /// 批量插入分块(内部按 BATCH_SIZE 分批)
    pub async fn insert_chunks(&self, rows: Vec<ChunkRow>) -> Result<(), String> {
        self.write_chunks("entities/insert", rows).await
    }

    /// 批量 upsert 分块(同 id 原地更新, 重向量化维度一致时使用)
    pub async fn upsert_chunks(&self, rows: Vec<ChunkRow>) -> Result<(), String> {
        self.write_chunks("entities/upsert", rows).await
    }

    /// 写入通用实现(insert/upsert 共用, 分批提交)
    async fn write_chunks(&self, path: &str, rows: Vec<ChunkRow>) -> Result<(), String> {
        for batch in rows.chunks(BATCH_SIZE) {
            let data: Vec<Value> = batch
                .iter()
                .map(|r| {
                    let mut v = serde_json::to_value(r).unwrap_or(Value::Null);
                    // JSON 字段 None → {}: 对齐 Python add 的空值填充(避免行丢失)
                    if let Some(obj) = v.as_object_mut() {
                        for key in ["position", "metadata"] {
                            if obj.get(key) == Some(&Value::Null) {
                                obj.insert(key.into(), json!({}));
                            }
                        }
                    }
                    v
                })
                .collect();
            self.call(
                path,
                json!({ "collectionName": CHUNK_COLLECTION, "data": data }),
            )
            .await?;
        }
        Ok(())
    }

    /// 按过滤表达式删除(filter 如 `document_id == "xxx"`)
    pub async fn delete_by_filter(&self, filter: &str) -> Result<(), String> {
        self.call(
            "entities/delete",
            json!({ "collectionName": CHUNK_COLLECTION, "filter": filter }),
        )
        .await
        .map(|_| ())
    }

    /// 按文档ID删除全部分块向量
    pub async fn delete_by_document(&self, document_id: &str) -> Result<(), String> {
        self.delete_by_filter(&format!("document_id == \"{document_id}\""))
            .await
    }

    /// 按项目ID删除全部分块向量
    pub async fn delete_by_project(&self, project_id: &str) -> Result<(), String> {
        self.delete_by_filter(&format!("project_id == \"{project_id}\""))
            .await
    }

    /// 混合检索: 稠密向量(语义) + 稀疏 BM25(关键词), 客户端 RRF 融合
    ///
    /// 对齐 Python dao.search 的 AnnSearchRequest×2 + RRFRanker 语义;
    /// 该 Milvus 版本的 REST hybrid_search 端点 ranker 兼容性差, 故分别调用
    /// entities/search 后按 RRF(倒数排名融合, k=60)在客户端合并,
    /// sparse 检索直接传原始文本(服务端 BM25 Function 处理)。
    pub async fn hybrid_search_chunks(
        &self,
        query_text: &str,
        query_vector: &[f64],
        project_ids: &[String],
        limit: i64,
    ) -> Result<Vec<ChunkHit>, String> {
        if !self.has_collection(CHUNK_COLLECTION).await? {
            return Ok(Vec::new());
        }
        let filter = project_filter(project_ids);
        let output_fields = json!([
            "id", "sort", "document_id", "project_id",
            "content", "source", "content_types", "position", "metadata"
        ]);
        // 两路检索请求体(向量路 data 嵌套数组, 稀疏路 data 传原始文本)
        let dense_body = json!({
            "collectionName": CHUNK_COLLECTION,
            "data": [query_vector],
            "annsField": "embedding",
            "limit": limit,
            "filter": filter,
            "outputFields": output_fields
        });
        let sparse_body = json!({
            "collectionName": CHUNK_COLLECTION,
            "data": [query_text],
            "annsField": "sparse",
            "limit": limit,
            "filter": filter,
            "outputFields": output_fields
        });
        // 两路并发检索(单路失败降级用另一路, 双路失败才报错)
        let (dense_res, sparse_res) =
            tokio::join!(self.call("entities/search", dense_body), self.call("entities/search", sparse_body));
        let dense_hits: Vec<ChunkHit> = match dense_res {
            Ok(resp) => parse_search_hits(&resp),
            Err(e) => {
                tracing::warn!("稠密向量检索失败(降级仅用关键词路): {e}");
                Vec::new()
            }
        };
        let sparse_hits: Vec<ChunkHit> = match sparse_res {
            Ok(resp) => parse_search_hits(&resp),
            Err(e) => {
                tracing::warn!("稀疏关键词检索失败(降级仅用向量路): {e}");
                Vec::new()
            }
        };
        if dense_hits.is_empty() && sparse_hits.is_empty() {
            return Ok(Vec::new());
        }
        // RRF 融合: score = Σ 1/(k + rank), rank 从 1 起; 仅单路命中时保留该路排序
        const K: f64 = 60.0;
        let mut merged: std::collections::HashMap<String, (ChunkHit, f64)> =
            std::collections::HashMap::new();
        for (rank, hit) in dense_hits.into_iter().enumerate() {
            let r = rank as f64 + 1.0;
            merged
                .entry(hit.id.clone())
                .or_insert_with(|| (hit, 0.0))
                .1 += 1.0 / (K + r);
        }
        for (rank, hit) in sparse_hits.into_iter().enumerate() {
            let r = rank as f64 + 1.0;
            merged
                .entry(hit.id.clone())
                .or_insert_with(|| (hit, 0.0))
                .1 += 1.0 / (K + r);
        }
        let mut hits: Vec<ChunkHit> = merged
            .into_values()
            .map(|(mut hit, score)| {
                hit.score = score;
                hit
            })
            .collect();
        hits.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap_or(std::cmp::Ordering::Equal));
        hits.truncate(limit as usize);
        Ok(hits)
    }

    /// 按过滤表达式查询实体(重向量化按文档读取全量分块用)
    pub async fn query_chunks(
        &self,
        filter: &str,
        limit: i64,
        offset: i64,
    ) -> Result<Vec<Value>, String> {
        let resp = self
            .call(
                "entities/query",
                json!({
                    "collectionName": CHUNK_COLLECTION,
                    "filter": filter,
                    "limit": limit,
                    "offset": offset,
                    "outputFields": [
                        "id", "sort", "document_id", "project_id",
                        "content", "source", "content_types", "position", "metadata"
                    ]
                }),
            )
            .await?;
        Ok(resp
            .get("data")
            .and_then(|d| d.as_array())
            .cloned()
            .unwrap_or_default())
    }
}

/// 项目过滤表达式(project_id in [...]; 空列表恒假)
fn project_filter(project_ids: &[String]) -> String {
    if project_ids.is_empty() {
        return "id == \"\"".to_string();
    }
    let ids: Vec<String> = project_ids
        .iter()
        .map(|id| format!("\"{id}\""))
        .collect();
    format!("project_id in [{}]", ids.join(","))
}

/// 解析 entities/search 响应 data 为 ChunkHit 列表(distance 顺带填入 score 占位)
fn parse_search_hits(resp: &Value) -> Vec<ChunkHit> {
    resp.get("data")
        .and_then(|d| d.as_array())
        .cloned()
        .unwrap_or_default()
        .into_iter()
        .map(|mut item| {
            // REST v2 命中的距离字段为 distance(暂存到 score, 融合阶段会被 RRF 分覆盖)
            let score = item
                .get("distance")
                .and_then(|d| d.as_f64())
                .or_else(|| item.get("score").and_then(|s| s.as_f64()))
                .unwrap_or(0.0);
            if let Some(obj) = item.as_object_mut() {
                obj.insert("score".into(), json!(score));
                obj.remove("distance");
                // 显式 null 一律移除(serde 的 default 只兜底缺失字段, 不兜底 null,
                // 否则 Vec<String> 等强类型字段会导致整个 ChunkHit 反序列化失败)
                obj.retain(|_, v| !v.is_null());
                // content_types 为 Milvus 内部包装格式 {"Data":{"StringData":{"data":[...]}}},
                // 解包为纯字符串数组
                if let Some(Value::Object(ct)) = obj.get("content_types") {
                    let flat = ct
                        .get("Data")
                        .and_then(|d| d.get("StringData"))
                        .and_then(|s| s.get("data"))
                        .cloned();
                    if let Some(flat) = flat {
                        obj.insert("content_types".into(), flat);
                    }
                }
                // position/metadata 为 JSON 字符串编码(如 "{}"), 解回 JSON 值
                for key in ["position", "metadata"] {
                    if let Some(Value::String(s)) = obj.get(key) {
                        if let Ok(v) = serde_json::from_str::<Value>(s) {
                            obj.insert(key.into(), v);
                        }
                    }
                }
            }
            match serde_json::from_value::<ChunkHit>(item) {
                Ok(hit) => hit,
                Err(e) => {
                    // 反序列化失败不应静默: 记录原因便于排查字段类型不匹配
                    tracing::warn!("检索命中反序列化失败(返回占位空块): {e}");
                    ChunkHit {
                        id: String::new(),
                        sort: 0,
                        document_id: String::new(),
                        project_id: String::new(),
                        content: String::new(),
                        source: String::new(),
                        content_types: Vec::new(),
                        position: Value::Null,
                        metadata: Value::Null,
                        score,
                    }
                }
            }
        })
        .collect()
}

// ==================== AppState 集成(全局装配与读取) ====================

/// 装配向量库客户端(启动钩子调用, 位于建表/动态配置种子之后)
///
/// 连接失败仅告警不阻断启动(检索功能降级为直答); 集合缺失时自动按默认维度创建。
pub async fn bootstrap(state: &crate::runtime::AppState) {
    let cfg = match state
        .settings
        .get::<DBVectorSettings>("db_vector")
        .await
    {
        Ok(cfg) => cfg,
        Err(e) => {
            tracing::warn!("读取向量库配置失败(向量功能停用): {e}");
            return;
        }
    };
    if cfg.r#type.is_empty() {
        return;
    }
    let client = Arc::new(MilvusClient::new(&cfg));
    match client.list_collections().await {
        Ok(names) => {
            tracing::info!("向量库连接成功: {} (集合 {} 个)", client_base(&client), names.len());
            if !names.iter().any(|n| n == CHUNK_COLLECTION) {
                // 集合缺失: 按默认维度创建(幂等, 对齐 Python create_all)
                if let Err(e) = client.create_chunk_collection(DEFAULT_EMBEDDING_DIM).await {
                    tracing::warn!("向量集合创建失败(检索功能降级): {e}");
                } else {
                    tracing::info!("向量集合 {CHUNK_COLLECTION} 已创建");
                }
            } else {
                // 已存在: 确保加载(对齐 Python connect_all 的 load_all)
                let _ = client.load_collection(CHUNK_COLLECTION).await;
            }
            *state.db_vector.write().await = Some(client);
        }
        Err(e) => {
            tracing::warn!("向量库连接失败(检索功能降级): {e}");
        }
    }
}

/// 获取已装配的向量库客户端(未启用/连接失败返回 None, 调用方按降级口径处理)
pub async fn get(state: &crate::runtime::AppState) -> Option<Arc<MilvusClient>> {
    state.db_vector.read().await.clone()
}

/// 客户端基地址(日志用; 不暴露内部结构)
fn client_base(c: &MilvusClient) -> String {
    c.base.clone()
}
