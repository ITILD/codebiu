//! 动态配置中心(对齐 Python common/config/dynamic)
//!
//! - 9 组配置(token/email/websearch/file_system/db_cache/db_vector/db_graph/tasks/admin)
//! - sys_config 表持久化, TTL 10s 缓存, 更新即时生效
//! - update: schema 感知深合并(未知字段 400 / secret 缺省保持 / 空串清除)
//! - describe: 字段元数据 + secret 打码, 直接驱动前端"通用配置"表单
//!
//! Rust 实现说明: 字段元数据用静态表声明(替代 Python 的 pydantic 反射),
//! 强类型校验通过各组 serde 结构体完成, 两者均以本文件为单一事实来源。

use chrono::Utc;
use sea_orm::{ActiveModelTrait, DatabaseConnection, EntityTrait, Set};
use serde::{Deserialize, Serialize, de::DeserializeOwned};
use serde_json::Value;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::Instant;

use crate::utils::error::AppError;
use crate::AppResult;
use crate::do_::entity::sys_config;

// ############################# 字段元数据声明 #############################

/// 表单控件类型(与 Python _field_type 输出一致)
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FieldType {
    Bool,
    Int,
    Float,
    Enum,
    Str,
    List,
    Secret,
}

impl FieldType {
    fn as_str(self) -> &'static str {
        match self {
            Self::Bool => "bool",
            Self::Int => "int",
            Self::Float => "float",
            Self::Enum => "enum",
            Self::Str => "str",
            Self::List => "list",
            Self::Secret => "secret",
        }
    }
}

/// 单个配置字段的静态元数据(key 为点路径, 嵌套子组如 "tavily.api_key")
#[derive(Debug, Clone, Copy)]
pub struct FieldDef {
    pub key: &'static str,
    pub title: &'static str,
    pub description: &'static str,
    pub ftype: FieldType,
    /// enum 类型候选项
    pub options: &'static [&'static str],
    /// 是否必填(pydantic is_required 语义; 本项目全部字段有默认值, 恒为 false)
    pub required: bool,
}

const fn f(key: &'static str, title: &'static str, ftype: FieldType) -> FieldDef {
    FieldDef { key, title, description: "", ftype, options: &[], required: false }
}

/// 带描述的字段定义
const fn fd(
    key: &'static str,
    title: &'static str,
    description: &'static str,
    ftype: FieldType,
) -> FieldDef {
    FieldDef { key, title, description, ftype, options: &[], required: false }
}

/// 带选项的 enum 字段定义
const fn fe(
    key: &'static str,
    title: &'static str,
    description: &'static str,
    options: &'static [&'static str],
) -> FieldDef {
    FieldDef { key, title, description, ftype: FieldType::Enum, options, required: false }
}

/// 配置组 schema(组元数据 + 拍平字段表 + 强类型校验入口)
pub struct GroupSchema {
    /// 组标识(sys_config.group 主键, 同时对应 config.yaml 同名节)
    pub group: &'static str,
    pub name: &'static str,
    pub description: &'static str,
    /// 连接级配置(改后需重启生效, 页面顶部标注)
    pub restart_required: bool,
    /// 密钥字段完整路径(回读打码/更新缺省保持)
    pub secrets: &'static [&'static str],
    /// 拍平字段元数据表(describe 输出顺序)
    pub fields: &'static [FieldDef],
    /// 默认值(完整嵌套 JSON, 首启种子兜底)
    pub defaults: fn() -> Value,
    /// 强类型校验 + 规范化(反序列化到结构体再序列化回 JSON)
    pub validate: fn(&Value) -> Result<Value, String>,
}

impl GroupSchema {
    /// 校验 patch 是否命中未知字段(点路径集合比对)
    fn check_unknown(&self, patch_flat: &HashMap<String, Value>) -> Result<(), String> {
        let known: std::collections::HashSet<&str> = self.fields.iter().map(|f| f.key).collect();
        let mut unknown: Vec<String> = patch_flat
            .keys()
            .filter(|k| !known.contains(k.as_str()))
            .cloned()
            .collect();
        unknown.sort();
        if unknown.is_empty() {
            Ok(())
        } else {
            Err(format!("未知配置字段: {}", unknown.join(", ")))
        }
    }
}

// ############################# 9 组强类型结构体 #############################

fn d(v: &str) -> String {
    v.to_string()
}

/// 令牌认证组
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TokenSettings {
    #[serde(default = "d_token_secret")]
    pub secret_key: String,
    #[serde(default = "d_hs256")]
    pub algorithm: String,
    #[serde(default = "d_30")]
    pub expire_minutes: i64,
    #[serde(default = "d_20")]
    pub refresh_expire_days: i64,
}
fn d_token_secret() -> String {
    d("test123456789123456789123456789123456789")
}
fn d_hs256() -> String {
    d("HS256")
}
fn d_30() -> i64 {
    30
}
fn d_20() -> i64 {
    20
}
impl Default for TokenSettings {
    fn default() -> Self {
        serde_json::from_value(Value::Null).unwrap_or(Self {
            secret_key: d_token_secret(),
            algorithm: d_hs256(),
            expire_minutes: 30,
            refresh_expire_days: 20,
        })
    }
}

/// 邮箱服务组
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmailSettings {
    #[serde(default = "d_smtp_qq")]
    pub smtp_server: String,
    #[serde(default = "d_465")]
    pub smtp_port: i64,
    #[serde(default)]
    pub sender_email: String,
    #[serde(default)]
    pub sender_password: String,
    #[serde(default)]
    pub sender_name: String,
    #[serde(default)]
    pub use_for_register: bool,
}
fn d_smtp_qq() -> String {
    d("smtp.qq.com")
}
fn d_465() -> i64 {
    465
}
impl EmailSettings {
    pub fn default_value() -> Value {
        serde_json::json!({
            "smtp_server": "smtp.qq.com", "smtp_port": 465, "sender_email": "",
            "sender_password": "", "sender_name": "", "use_for_register": false
        })
    }
}

/// Tavily 子组
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TavilySettings {
    #[serde(default)]
    pub api_key: String,
    #[serde(default = "d_basic")]
    pub search_depth: String,
    #[serde(default)]
    pub include_answer: bool,
}

impl Default for TavilySettings {
    fn default() -> Self {
        Self {
            api_key: String::new(),
            search_depth: d_basic(),
            include_answer: false,
        }
    }
}

fn d_basic() -> String {
    d("basic")
}

/// Firecrawl 子组
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FirecrawlSettings {
    #[serde(default)]
    pub api_key: String,
    #[serde(default = "d_firecrawl_base")]
    pub api_base: String,
}

impl Default for FirecrawlSettings {
    fn default() -> Self {
        Self {
            api_key: String::new(),
            api_base: d_firecrawl_base(),
        }
    }
}

fn d_firecrawl_base() -> String {
    d("https://api.firecrawl.dev")
}

/// 网页搜索组
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WebSearchSettings {
    #[serde(default = "d_ddg")]
    pub default_engine: String,
    #[serde(default = "d_15f")]
    pub timeout: f64,
    #[serde(default = "d_10")]
    pub max_results: i64,
    #[serde(default)]
    pub proxy: Option<String>,
    #[serde(default)]
    pub tavily: TavilySettings,
    #[serde(default)]
    pub firecrawl: FirecrawlSettings,
}
fn d_ddg() -> String {
    d("duckduckgo")
}
fn d_15f() -> f64 {
    15.0
}
fn d_10() -> i64 {
    10
}

/// 文件存储组
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileSystemSettings {
    #[serde(default = "d_s3")]
    pub storage_type: String,
    #[serde(default = "d_10f")]
    pub max_size: f64,
    #[serde(default = "d_allowed_ext")]
    pub allowed_extensions: Vec<String>,
    #[serde(default)]
    pub endpoint_url: String,
    #[serde(default)]
    pub access_key: String,
    #[serde(default)]
    pub secret_key: String,
    #[serde(default)]
    pub bucket: String,
    #[serde(default = "d_region")]
    pub region: String,
    #[serde(default)]
    pub secure: bool,
}
fn d_s3() -> String {
    d("s3")
}
fn d_10f() -> f64 {
    10.0
}
fn d_region() -> String {
    d("us-east-1")
}
fn d_allowed_ext() -> Vec<String> {
    vec![
        d("application/zip"),
        d("application/pdf"),
        d("image/*"),
        d("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ]
}

/// 缓存数据库组
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DBCacheSettings {
    #[serde(default = "d_redis")]
    pub r#type: String,
    #[serde(default)]
    pub db: i64,
    #[serde(default = "d_localhost")]
    pub host: String,
    #[serde(default = "d_6379")]
    pub port: i64,
    #[serde(default)]
    pub password: String,
    #[serde(default = "d_redis_db")]
    pub database: String,
}
fn d_redis() -> String {
    d("redis")
}
fn d_localhost() -> String {
    d("127.0.0.1")
}
fn d_6379() -> i64 {
    6379
}
fn d_redis_db() -> String {
    d("temp_source/db/redis.db")
}

/// 向量数据库组
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DBVectorSettings {
    #[serde(default = "d_milvus")]
    pub r#type: String,
    #[serde(default = "d_milvus_host")]
    pub host: String,
    #[serde(default = "d_19530")]
    pub port: i64,
    #[serde(default = "d_root")]
    pub user: String,
    #[serde(default)]
    pub password: Option<String>,
    #[serde(default = "d_default_db")]
    pub database: String,
}
fn d_milvus() -> String {
    d("milvus")
}
fn d_milvus_host() -> String {
    d("http://127.0.0.1")
}
fn d_19530() -> i64 {
    19530
}
fn d_root() -> String {
    d("root")
}
fn d_default_db() -> String {
    d("default")
}

/// 图数据库组
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DBGraphSettings {
    #[serde(default = "d_graph_local")]
    pub r#type: String,
    #[serde(default = "d_graph_db")]
    pub database: String,
    #[serde(default)]
    pub host: Option<String>,
    #[serde(default)]
    pub port: Option<i64>,
    #[serde(default)]
    pub user: Option<String>,
    #[serde(default)]
    pub password: Option<String>,
}
fn d_graph_local() -> String {
    d("graph_local")
}
fn d_graph_db() -> String {
    d("temp_source/db/db_graph_local.db")
}

/// 任务队列组
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TasksSettings {
    #[serde(default = "d_local_engine")]
    pub engine: String,
    #[serde(default = "d_memory_broker")]
    pub broker_url: String,
    #[serde(default = "d_cache_backend")]
    pub result_backend: String,
}
fn d_local_engine() -> String {
    d("local")
}
fn d_memory_broker() -> String {
    d("memory://")
}
fn d_cache_backend() -> String {
    d("cache+memory://")
}

/// 默认管理员组
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AdminSettings {
    #[serde(default = "d_admin")]
    pub username: String,
    #[serde(default = "d_admin123")]
    pub password: String,
    #[serde(default = "d_admin_nick")]
    pub nickname: String,
    #[serde(default = "d_admin_email")]
    pub email: String,
    #[serde(default)]
    pub reset_password: bool,
}
fn d_admin() -> String {
    d("admin")
}
fn d_admin123() -> String {
    d("admin123")
}
fn d_admin_nick() -> String {
    d("系统管理员")
}
fn d_admin_email() -> String {
    d("admin@codebiu.local")
}

// ############################# 组注册表(单一事实来源) #############################

fn validate<T: DeserializeOwned + Serialize>(v: &Value) -> Result<Value, String> {
    let parsed: T =
        serde_json::from_value(v.clone()).map_err(|e| format!("配置校验失败: {e}"))?;
    serde_json::to_value(parsed).map_err(|e| format!("配置序列化失败: {e}"))
}

fn token_defaults() -> Value {
    serde_json::json!({
        "secret_key": "test123456789123456789123456789123456789",
        "algorithm": "HS256", "expire_minutes": 30, "refresh_expire_days": 20
    })
}
fn websearch_defaults() -> Value {
    serde_json::json!({
        "default_engine": "duckduckgo", "timeout": 15, "max_results": 10, "proxy": null,
        "tavily": {"api_key": "", "search_depth": "basic", "include_answer": false},
        "firecrawl": {"api_key": "", "api_base": "https://api.firecrawl.dev"}
    })
}
fn file_system_defaults() -> Value {
    serde_json::json!({
        "storage_type": "s3", "max_size": 10,
        "allowed_extensions": [
            "application/zip", "application/pdf", "image/*",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ],
        "endpoint_url": "", "access_key": "", "secret_key": "", "bucket": "",
        "region": "us-east-1", "secure": false
    })
}
fn db_cache_defaults() -> Value {
    serde_json::json!({
        "type": "redis", "db": 0, "host": "127.0.0.1", "port": 6379,
        "password": "", "database": "temp_source/db/redis.db"
    })
}
fn db_vector_defaults() -> Value {
    serde_json::json!({
        "type": "milvus", "host": "http://127.0.0.1", "port": 19530,
        "user": "root", "password": null, "database": "default"
    })
}
fn db_graph_defaults() -> Value {
    serde_json::json!({
        "type": "graph_local", "database": "temp_source/db/db_graph_local.db",
        "host": null, "port": null, "user": null, "password": null
    })
}
fn tasks_defaults() -> Value {
    serde_json::json!({
        "engine": "local", "broker_url": "memory://", "result_backend": "cache+memory://"
    })
}
fn admin_defaults() -> Value {
    serde_json::json!({
        "username": "admin", "password": "admin123", "nickname": "系统管理员",
        "email": "admin@codebiu.local", "reset_password": false
    })
}

/// 全部配置组(UI 展示顺序即此顺序)
pub static GROUPS: &[GroupSchema] = &[
    GroupSchema {
        group: "token",
        name: "令牌认证",
        description: "JWT 签名与有效期; 修改签名密钥会使所有已登录用户令牌失效(需重新登录)",
        restart_required: false,
        secrets: &["secret_key"],
        fields: &[
            fd("secret_key", "签名密钥", "JWT 签名密钥(≥32位随机字符串)", FieldType::Secret),
            f("algorithm", "签名算法", FieldType::Str),
            fd("expire_minutes", "访问令牌有效期(分钟)", "", FieldType::Int),
            fd("refresh_expire_days", "刷新令牌有效期(天)", "", FieldType::Int),
        ],
        defaults: token_defaults,
        validate: |v| validate::<TokenSettings>(v),
    },
    GroupSchema {
        group: "email",
        name: "邮箱服务",
        description: "SMTP 发件配置; 用于注册验证码等邮件发送",
        restart_required: false,
        secrets: &["sender_password"],
        fields: &[
            f("smtp_server", "SMTP 服务器", FieldType::Str),
            f("smtp_port", "SMTP 端口", FieldType::Int),
            f("sender_email", "发件邮箱", FieldType::Str),
            fd("sender_password", "SMTP 授权码", "邮箱服务商提供的授权码(非登录密码); 为空视为未配置", FieldType::Secret),
            f("sender_name", "发件人名称", FieldType::Str),
            fd("use_for_register", "注册需邮箱验证", "开启后注册需先获取邮件验证码", FieldType::Bool),
        ],
        defaults: || EmailSettings::default_value(),
        validate: |v| validate::<EmailSettings>(v),
    },
    GroupSchema {
        group: "websearch",
        name: "网页搜索",
        description: "module_websearch 模块全局参数(duckduckgo 直连无需密钥)",
        restart_required: false,
        secrets: &["tavily.api_key", "firecrawl.api_key"],
        fields: &[
            fe("default_engine", "默认搜索引擎", "", &["duckduckgo", "tavily", "firecrawl"]),
            f("timeout", "请求超时(秒)", FieldType::Float),
            f("max_results", "默认返回条数上限", FieldType::Int),
            fd("proxy", "出网代理", "为空直连; 如 http://127.0.0.1:7890", FieldType::Str),
            fd("tavily.api_key", "API Key", "https://app.tavily.com 免费注册获取; 为空则该引擎不可用", FieldType::Secret),
            fe("tavily.search_depth", "搜索深度", "advanced 更全但更慢、消耗额度更多", &["basic", "advanced"]),
            fd("tavily.include_answer", "返回 AI 摘要答案", "", FieldType::Bool),
            fd("firecrawl.api_key", "API Key", "https://www.firecrawl.dev 免费注册获取; 为空则该引擎不可用", FieldType::Secret),
            fd("firecrawl.api_base", "API 地址", "可替换为自部署实例地址", FieldType::Str),
        ],
        defaults: websearch_defaults,
        validate: |v| validate::<WebSearchSettings>(v),
    },
    GroupSchema {
        group: "file_system",
        name: "文件存储",
        description: "上传限额即时生效; 存储类型与连接信息变更需重启(切换存储请先走文件迁移流程)",
        restart_required: true,
        secrets: &["access_key", "secret_key"],
        fields: &[
            fe("storage_type", "存储类型", "", &["local", "s3", "rustfs"]),
            f("max_size", "上传大小限制(MB)", FieldType::Float),
            f("allowed_extensions", "允许的 MIME 类型", FieldType::List),
            fd("endpoint_url", "S3 Endpoint", "S3/MinIO/rustfs 地址, 如 http://127.0.0.1:9000", FieldType::Str),
            f("access_key", "Access Key", FieldType::Secret),
            f("secret_key", "Secret Key", FieldType::Secret),
            f("bucket", "存储桶", FieldType::Str),
            f("region", "Region", FieldType::Str),
            f("secure", "启用 HTTPS", FieldType::Bool),
        ],
        defaults: file_system_defaults,
        validate: |v| validate::<FileSystemSettings>(v),
    },
    GroupSchema {
        group: "db_cache",
        name: "缓存数据库",
        description: "Redis/Fakeredis 连接; 变更需重启生效",
        restart_required: true,
        secrets: &["password"],
        fields: &[
            fd("type", "类型", "redis / fakeredis(本地内存)", FieldType::Str),
            f("db", "逻辑库编号", FieldType::Int),
            f("host", "主机", FieldType::Str),
            f("port", "端口", FieldType::Int),
            f("password", "密码", FieldType::Secret),
            fd("database", "持久化文件", "Fakeredis 持久化地址; Redis 模式留作记录", FieldType::Str),
        ],
        defaults: db_cache_defaults,
        validate: |v| validate::<DBCacheSettings>(v),
    },
    GroupSchema {
        group: "db_vector",
        name: "向量数据库",
        description: "Milvus/LanceDB 连接; 变更需重启生效, 更换向量库后需重建向量索引",
        restart_required: true,
        secrets: &["password"],
        fields: &[
            fd("type", "类型", "milvus / lancedb(本地文件)", FieldType::Str),
            fd("host", "主机", "milvus 专用", FieldType::Str),
            fd("port", "端口", "milvus 专用", FieldType::Int),
            fd("user", "用户名", "milvus 专用", FieldType::Str),
            fd("password", "密码", "milvus 专用", FieldType::Secret),
            fd("database", "数据库", "milvus 为库名; lancedb 为本地目录路径", FieldType::Str),
        ],
        defaults: db_vector_defaults,
        validate: |v| validate::<DBVectorSettings>(v),
    },
    GroupSchema {
        group: "db_graph",
        name: "图数据库",
        description: "graph_local/neo4j 连接; 变更需重启生效",
        restart_required: true,
        secrets: &["password"],
        fields: &[
            fd("type", "类型", "graph_local(本地文件) / neo4j", FieldType::Str),
            fd("database", "数据库", "graph_local 为文件路径; neo4j 为库名", FieldType::Str),
            fd("host", "主机", "neo4j 专用", FieldType::Str),
            fd("port", "端口", "neo4j 专用", FieldType::Int),
            fd("user", "用户名", "neo4j 专用", FieldType::Str),
            fd("password", "密码", "neo4j 专用", FieldType::Secret),
        ],
        defaults: db_graph_defaults,
        validate: |v| validate::<DBGraphSettings>(v),
    },
    GroupSchema {
        group: "tasks",
        name: "任务队列",
        description: "engine 切换(local=进程内协程/celery=Redis worker)对新建任务即时生效; broker 地址变更需重启 worker",
        restart_required: false,
        secrets: &["broker_url", "result_backend"],
        fields: &[
            fe("engine", "执行引擎", "", &["local", "celery"]),
            fd("broker_url", "Broker 地址", "celery 引擎的 Redis broker(与缓存库同实例分库)", FieldType::Secret),
            fd("result_backend", "结果后端", "celery 引擎的结果回写地址", FieldType::Secret),
        ],
        defaults: tasks_defaults,
        validate: |v| validate::<TasksSettings>(v),
    },
    GroupSchema {
        group: "admin",
        name: "默认管理员",
        description: "启动引导账户(绑定全局 admin 角色); reset_password 开启时每次启动将密码重置为配置值(忘记密码自救)",
        restart_required: false,
        secrets: &["password"],
        fields: &[
            f("username", "用户名", FieldType::Str),
            fd("password", "密码", "引导创建/重置用; 日常改密请走用户管理", FieldType::Secret),
            f("nickname", "昵称", FieldType::Str),
            f("email", "邮箱", FieldType::Str),
            f("reset_password", "启动时重置密码", FieldType::Bool),
        ],
        defaults: admin_defaults,
        validate: |v| validate::<AdminSettings>(v),
    },
];

fn schema_of(group: &str) -> AppResult<&'static GroupSchema> {
    GROUPS
        .iter()
        .find(|g| g.group == group)
        .ok_or_else(|| AppError::business(format!("未知配置组: {group}")))
}

/// 点路径取值(如 "tavily.api_key" 在嵌套 JSON 中定位)
fn get_at<'a>(value: &'a Value, path: &str) -> Option<&'a Value> {
    let mut cursor = value;
    for seg in path.split('.') {
        cursor = cursor.get(seg)?;
    }
    Some(cursor)
}

/// 点路径写值(逐级创建缺失的对象节点)
fn set_at(value: &mut Value, path: &str, new_val: Value) {
    let mut cursor = value;
    let segs: Vec<&str> = path.split('.').collect();
    for seg in &segs[..segs.len() - 1] {
        if !cursor.is_object() {
            *cursor = serde_json::json!({});
        }
        cursor = cursor
            .as_object_mut()
            .expect("已确保为对象")
            .entry(seg.to_string())
            .or_insert(serde_json::json!({}));
    }
    if !cursor.is_object() {
        *cursor = serde_json::json!({});
    }
    cursor
        .as_object_mut()
        .expect("已确保为对象")
        .insert(segs[segs.len() - 1].to_string(), new_val);
}

/// patch 嵌套 JSON 拍平为点路径映射(list/标量整体保留)
fn flatten(value: &Value, prefix: &str, out: &mut HashMap<String, Value>) {
    match value {
        Value::Object(map) => {
            for (k, v) in map {
                let path = if prefix.is_empty() {
                    k.clone()
                } else {
                    format!("{prefix}.{k}")
                };
                flatten(v, &path, out);
            }
        }
        other => {
            // 前缀为空说明顶层是标量(非法 patch), 仍记录以便报未知字段
            if prefix.is_empty() {
                out.insert("__root__".to_string(), other.clone());
            } else {
                out.insert(prefix.to_string(), other.clone());
            }
        }
    }
}

// ############################# 服务 #############################

/// 动态配置服务(进程级单例, 持数据库连接)
pub struct SettingsService {
    db: DatabaseConnection,
    /// TTL 缓存: 组名 -> (写入时刻, 当前值)
    cache: Mutex<HashMap<String, (Instant, Value)>>,
}

impl SettingsService {
    /// TTL 10s(其他进程如 worker 的陈旧窗口)
    const TTL: std::time::Duration = std::time::Duration::from_secs(10);

    pub fn new(db: DatabaseConnection) -> Arc<Self> {
        Arc::new(Self { db, cache: Mutex::new(HashMap::new()) })
    }

    /// 按组读取当前值(默认值 + 库行深合并, TTL 缓存)
    pub async fn get_raw(&self, group: &str) -> AppResult<Value> {
        schema_of(group)?;
        if let Some((at, value)) = self.cache.lock().expect("缓存锁").get(group) {
            if at.elapsed() <= Self::TTL {
                return Ok(value.clone());
            }
        }
        let row = sys_config::Entity::find_by_id(group)
            .one(&self.db)
            .await?
            .map(|r| r.value.unwrap_or_else(|| serde_json::json!({})))
            .unwrap_or_else(|| serde_json::json!({}));
        let schema = schema_of(group)?;
        let mut merged = (schema.defaults)();
        crate::config::deep_merge(&mut merged, &row);
        // 规范化(类型纠正/默认兜底)
        let value = (schema.validate)(&merged)
            .map_err(AppError::business)?;
        self.cache
            .lock()
            .expect("缓存锁")
            .insert(group.to_string(), (Instant::now(), value.clone()));
        Ok(value)
    }

    /// 类型化读取(反序列化到强类型结构体)
    pub async fn get<T: DeserializeOwned>(&self, group: &str) -> AppResult<T> {
        let raw = self.get_raw(group).await?;
        serde_json::from_value(raw)
            .map_err(|e| AppError::Internal(format!("配置反序列化失败: {e}")))
    }

    /// 更新配置组: 未知字段 400 / secret 缺省保持 / 空串清除 / 校验落库 / 缓存失效
    pub async fn update(
        &self,
        group: &str,
        patch: &Value,
        updated_by: &str,
    ) -> AppResult<()> {
        let schema = schema_of(group)?;
        if !patch.is_object() {
            return Err(AppError::business("配置更新数据必须是对象"));
        }
        let mut patch_flat = HashMap::new();
        flatten(patch, "", &mut patch_flat);
        schema.check_unknown(&patch_flat).map_err(AppError::business)?;

        let old = self.get_raw(group).await?;
        let mut merged = old;
        for (path, value) in patch_flat {
            // secret 字段: null/空串=清除, 有值=覆盖
            let new_val = if schema.secrets.contains(&path.as_str())
                && (value.is_null() || matches!(&value, Value::String(s) if s.is_empty()))
            {
                Value::String(String::new())
            } else {
                value
            };
            set_at(&mut merged, &path, new_val);
        }
        // 强类型校验 + 规范化(校验失败 → 400)
        let normalized = (schema.validate)(&merged).map_err(AppError::business)?;

        self.upsert_row(group, &normalized, Some(updated_by)).await?;
        // 写入即刷新缓存(即时生效)
        self.cache
            .lock()
            .expect("缓存锁")
            .insert(group.to_string(), (Instant::now(), normalized));
        Ok(())
    }

    /// sys_config 表 upsert(version 递增, updated_at 刷新)
    async fn upsert_row(
        &self,
        group: &str,
        value: &Value,
        updated_by: Option<&str>,
    ) -> AppResult<()> {
        let existing = sys_config::Entity::find_by_id(group).one(&self.db).await?;
        let now = Utc::now().fixed_offset();
        match existing {
            Some(row) => {
                let new_version = row.version + 1;
                let mut am: sys_config::ActiveModel = row.into();
                am.value = Set(Some(value.clone()));
                am.version = Set(new_version);
                if let Some(by) = updated_by {
                    am.updated_by = Set(Some(by.to_string()));
                }
                am.updated_at = Set(now);
                am.update(&self.db).await?;
            }
            None => {
                sys_config::ActiveModel {
                    group: Set(group.to_string()),
                    value: Set(Some(value.clone())),
                    version: Set(1),
                    updated_by: Set(updated_by.map(|s| s.to_string())),
                    updated_at: Set(now),
                }
                .insert(&self.db)
                .await?;
            }
        }
        Ok(())
    }

    /// 单组描述(元数据 + 打码值, 驱动前端表单)
    pub async fn describe(&self, group: &str) -> AppResult<Value> {
        let schema = schema_of(group)?;
        let row = sys_config::Entity::find_by_id(group).one(&self.db).await?;
        let dump = self.get_raw(group).await?;
        let fields: Vec<Value> = schema
            .fields
            .iter()
            .map(|fdef| {
                let mut meta = serde_json::json!({
                    "key": fdef.key,
                    "title": fdef.title,
                    "description": fdef.description,
                    "type": fdef.ftype.as_str(),
                    "options": if fdef.options.is_empty() { Value::Null } else { serde_json::json!(fdef.options) },
                    "required": fdef.required,
                });
                let obj = meta.as_object_mut().expect("json 对象");
                if fdef.ftype == FieldType::Secret {
                    let has = get_at(&dump, fdef.key)
                        .map(|v| matches!(v, Value::String(s) if !s.is_empty()))
                        .unwrap_or(false);
                    obj.insert("value".into(), Value::Null);
                    obj.insert("has_value".into(), serde_json::json!(has));
                } else {
                    let value = get_at(&dump, fdef.key).cloned().unwrap_or(Value::Null);
                    obj.insert("value".into(), value);
                }
                meta
            })
            .collect();
        Ok(serde_json::json!({
            "group": schema.group,
            "name": schema.name,
            "description": schema.description,
            "restart_required": schema.restart_required,
            "updated_at": row.as_ref().map(|r| r.updated_at.to_rfc3339()),
            "updated_by": row.as_ref().and_then(|r| r.updated_by.clone()),
            "fields": fields,
        }))
    }

    /// 全部组描述
    pub async fn describe_all(&self) -> AppResult<Vec<Value>> {
        let mut result = Vec::with_capacity(GROUPS.len());
        for schema in GROUPS {
            result.push(self.describe(schema.group).await?);
        }
        Ok(result)
    }

    /// 首启种子: 组行不存在时, 以 yaml 同名节覆盖默认值建行(幂等, 不覆盖已有行)
    pub async fn seed_from_yaml(&self, raw_config: &Value) -> AppResult<()> {
        for schema in GROUPS {
            if sys_config::Entity::find_by_id(schema.group)
                .one(&self.db)
                .await?
                .is_some()
            {
                continue;
            }
            let section = raw_config.get(schema.group).cloned().unwrap_or(Value::Null);
            let mut merged = (schema.defaults)();
            crate::config::deep_merge(&mut merged, &section);
            let value = (schema.validate)(&merged).map_err(AppError::business)?;
            self.upsert_row(schema.group, &value, Some("seed")).await?;
            tracing::info!("动态配置组 '{}' 已按 yaml 种子初始化", schema.group);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn 拍平与点路径读写() {
        let patch = serde_json::json!({"tavily": {"api_key": "k"}, "max_results": 5});
        let mut flat = HashMap::new();
        flatten(&patch, "", &mut flat);
        assert_eq!(flat.len(), 2);
        assert!(flat.contains_key("tavily.api_key"));
        assert!(flat.contains_key("max_results"));

        let mut v = serde_json::json!({"tavily": {"api_key": ""}});
        set_at(&mut v, "tavily.api_key", serde_json::json!("x"));
        assert_eq!(v["tavily"]["api_key"], "x");
        set_at(&mut v, "firecrawl.api_base", serde_json::json!("http://a"));
        assert_eq!(v["firecrawl"]["api_base"], "http://a");
    }

    #[test]
    fn 未知字段检测() {
        let schema = schema_of("token").unwrap();
        let mut flat = HashMap::new();
        flat.insert("expire_minutes".to_string(), serde_json::json!(60));
        flat.insert("bad_field".to_string(), serde_json::json!(1));
        assert!(schema.check_unknown(&flat).is_err());
        flat.remove("bad_field");
        assert!(schema.check_unknown(&flat).is_ok());
    }

    #[test]
    fn 强类型校验与默认兜底() {
        let schema = schema_of("token").unwrap();
        let value = (schema.validate)(&serde_json::json!({})).unwrap();
        assert_eq!(value["expire_minutes"], 30);
        assert!((schema.validate)(&serde_json::json!({"expire_minutes": "abc"})).is_err());
    }
}
