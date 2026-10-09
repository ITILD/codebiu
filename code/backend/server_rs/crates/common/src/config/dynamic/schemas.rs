//! 配置组 schema 声明(对齐 Python config/dynamic/schemas.py)
//!
//! 单一事实来源: 每组的 强类型结构体(serde 默认值即业务默认值) + 字段元数据表
//! + 密钥路径 + 默认值 JSON(由 Default 派生) 都在本文件声明。
//! 新增配置组 = 在此加结构体 + Default + GROUPS 一项。

use serde::{Deserialize, Serialize, de::DeserializeOwned};
use serde_json::Value;
use std::collections::HashMap;

use crate::utils::error::AppError;
use crate::AppResult;

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
    pub fn as_str(self) -> &'static str {
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

/// 无描述字段定义
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
    /// 默认值(完整嵌套 JSON, 首启种子兜底; 由结构体 Default 派生)
    pub defaults: fn() -> Value,
    /// 强类型校验 + 规范化(反序列化到结构体再序列化回 JSON)
    pub validate: fn(&Value) -> Result<Value, String>,
}

impl GroupSchema {
    /// 校验 patch 是否命中未知字段(点路径集合比对)
    pub fn check_unknown(&self, patch_flat: &HashMap<String, Value>) -> Result<(), String> {
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

/// 结构体 Default → 默认值 JSON(与 serde 字段默认值同源)
fn defaults<T: Serialize + Default>() -> Value {
    serde_json::to_value(T::default()).expect("默认配置序列化失败")
}

/// 强类型校验 + 规范化(校验失败文案带回 serde 详情)
fn validate<T: DeserializeOwned + Serialize>(v: &Value) -> Result<Value, String> {
    let parsed: T = serde_json::from_value(v.clone()).map_err(|e| format!("配置校验失败: {e}"))?;
    serde_json::to_value(parsed).map_err(|e| format!("配置序列化失败: {e}"))
}

/// 按组标识取 schema(未知组 → 400)
pub fn schema_of(group: &str) -> AppResult<&'static GroupSchema> {
    GROUPS
        .iter()
        .find(|g| g.group == group)
        .ok_or_else(|| AppError::business(format!("未知配置组: {group}")))
}

// ############################# 9 组强类型结构体 #############################
// serde(default) 函数即业务默认值(与 config.yaml 基线一致), Default impl 复用之。

fn d(v: &str) -> String {
    v.to_string()
}

/// 令牌认证组
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TokenSettings {
    #[serde(default = "default_token_secret")]
    pub secret_key: String,
    #[serde(default = "default_algorithm")]
    pub algorithm: String,
    #[serde(default = "default_expire_minutes")]
    pub expire_minutes: i64,
    #[serde(default = "default_refresh_days")]
    pub refresh_expire_days: i64,
}
fn default_token_secret() -> String {
    d("test123456789123456789123456789123456789")
}
fn default_algorithm() -> String {
    d("HS256")
}
fn default_expire_minutes() -> i64 {
    30
}
fn default_refresh_days() -> i64 {
    20
}
impl Default for TokenSettings {
    fn default() -> Self {
        Self {
            secret_key: default_token_secret(),
            algorithm: default_algorithm(),
            expire_minutes: default_expire_minutes(),
            refresh_expire_days: default_refresh_days(),
        }
    }
}

/// 邮箱服务组
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmailSettings {
    #[serde(default = "default_smtp_server")]
    pub smtp_server: String,
    #[serde(default = "default_smtp_port")]
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
fn default_smtp_server() -> String {
    d("smtp.qq.com")
}
fn default_smtp_port() -> i64 {
    465
}
impl Default for EmailSettings {
    fn default() -> Self {
        Self {
            smtp_server: default_smtp_server(),
            smtp_port: default_smtp_port(),
            sender_email: String::new(),
            sender_password: String::new(),
            sender_name: String::new(),
            use_for_register: false,
        }
    }
}

/// Tavily 子组
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TavilySettings {
    #[serde(default)]
    pub api_key: String,
    #[serde(default = "default_search_depth")]
    pub search_depth: String,
    #[serde(default)]
    pub include_answer: bool,
}
fn default_search_depth() -> String {
    d("basic")
}
impl Default for TavilySettings {
    fn default() -> Self {
        Self { api_key: String::new(), search_depth: default_search_depth(), include_answer: false }
    }
}

/// Firecrawl 子组
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FirecrawlSettings {
    #[serde(default)]
    pub api_key: String,
    #[serde(default = "default_firecrawl_base")]
    pub api_base: String,
}
fn default_firecrawl_base() -> String {
    d("https://api.firecrawl.dev")
}
impl Default for FirecrawlSettings {
    fn default() -> Self {
        Self { api_key: String::new(), api_base: default_firecrawl_base() }
    }
}

/// 网页搜索组
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WebSearchSettings {
    #[serde(default = "default_search_engine")]
    pub default_engine: String,
    #[serde(default = "default_search_timeout")]
    pub timeout: f64,
    #[serde(default = "default_max_results")]
    pub max_results: i64,
    #[serde(default)]
    pub proxy: Option<String>,
    #[serde(default)]
    pub tavily: TavilySettings,
    #[serde(default)]
    pub firecrawl: FirecrawlSettings,
}
fn default_search_engine() -> String {
    d("duckduckgo")
}
fn default_search_timeout() -> f64 {
    15.0
}
fn default_max_results() -> i64 {
    10
}
impl Default for WebSearchSettings {
    fn default() -> Self {
        Self {
            default_engine: default_search_engine(),
            timeout: default_search_timeout(),
            max_results: default_max_results(),
            proxy: None,
            tavily: TavilySettings::default(),
            firecrawl: FirecrawlSettings::default(),
        }
    }
}

/// 文件存储组
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileSystemSettings {
    #[serde(default = "default_storage_type")]
    pub storage_type: String,
    #[serde(default = "default_max_size_mb")]
    pub max_size: f64,
    #[serde(default = "default_allowed_extensions")]
    pub allowed_extensions: Vec<String>,
    #[serde(default)]
    pub endpoint_url: String,
    #[serde(default)]
    pub access_key: String,
    #[serde(default)]
    pub secret_key: String,
    #[serde(default)]
    pub bucket: String,
    #[serde(default = "default_s3_region")]
    pub region: String,
    #[serde(default)]
    pub secure: bool,
}
fn default_storage_type() -> String {
    d("s3")
}
fn default_max_size_mb() -> f64 {
    10.0
}
fn default_s3_region() -> String {
    d("us-east-1")
}
fn default_allowed_extensions() -> Vec<String> {
    vec![
        d("application/zip"),
        d("application/pdf"),
        d("image/*"),
        d("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ]
}
impl Default for FileSystemSettings {
    fn default() -> Self {
        Self {
            storage_type: default_storage_type(),
            max_size: default_max_size_mb(),
            allowed_extensions: default_allowed_extensions(),
            endpoint_url: String::new(),
            access_key: String::new(),
            secret_key: String::new(),
            bucket: String::new(),
            region: default_s3_region(),
            secure: false,
        }
    }
}

/// 缓存数据库组
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DBCacheSettings {
    #[serde(default = "default_cache_type")]
    pub r#type: String,
    #[serde(default)]
    pub db: i64,
    #[serde(default = "default_localhost")]
    pub host: String,
    #[serde(default = "default_redis_port")]
    pub port: i64,
    #[serde(default)]
    pub password: String,
    #[serde(default = "default_cache_database")]
    pub database: String,
}
fn default_cache_type() -> String {
    d("redis")
}
fn default_localhost() -> String {
    d("127.0.0.1")
}
fn default_redis_port() -> i64 {
    6379
}
fn default_cache_database() -> String {
    d("temp_source/db/redis.db")
}
impl Default for DBCacheSettings {
    fn default() -> Self {
        Self {
            r#type: default_cache_type(),
            db: 0,
            host: default_localhost(),
            port: default_redis_port(),
            password: String::new(),
            database: default_cache_database(),
        }
    }
}

/// 向量数据库组
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DBVectorSettings {
    #[serde(default = "default_vector_type")]
    pub r#type: String,
    #[serde(default = "default_milvus_host")]
    pub host: String,
    #[serde(default = "default_milvus_port")]
    pub port: i64,
    #[serde(default = "default_milvus_user")]
    pub user: String,
    #[serde(default)]
    pub password: Option<String>,
    #[serde(default = "default_vector_database")]
    pub database: String,
}
fn default_vector_type() -> String {
    d("milvus")
}
fn default_milvus_host() -> String {
    d("http://127.0.0.1")
}
fn default_milvus_port() -> i64 {
    19530
}
fn default_milvus_user() -> String {
    d("root")
}
fn default_vector_database() -> String {
    d("default")
}
impl Default for DBVectorSettings {
    fn default() -> Self {
        Self {
            r#type: default_vector_type(),
            host: default_milvus_host(),
            port: default_milvus_port(),
            user: default_milvus_user(),
            password: None,
            database: default_vector_database(),
        }
    }
}

/// 图数据库组
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DBGraphSettings {
    #[serde(default = "default_graph_type")]
    pub r#type: String,
    #[serde(default = "default_graph_database")]
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
fn default_graph_type() -> String {
    d("graph_local")
}
fn default_graph_database() -> String {
    d("temp_source/db/db_graph_local.db")
}
impl Default for DBGraphSettings {
    fn default() -> Self {
        Self {
            r#type: default_graph_type(),
            database: default_graph_database(),
            host: None,
            port: None,
            user: None,
            password: None,
        }
    }
}

/// 任务队列组
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TasksSettings {
    #[serde(default = "default_task_engine")]
    pub engine: String,
    #[serde(default = "default_broker_url")]
    pub broker_url: String,
    #[serde(default = "default_result_backend")]
    pub result_backend: String,
}
fn default_task_engine() -> String {
    d("local")
}
fn default_broker_url() -> String {
    d("memory://")
}
fn default_result_backend() -> String {
    d("cache+memory://")
}
impl Default for TasksSettings {
    fn default() -> Self {
        Self {
            engine: default_task_engine(),
            broker_url: default_broker_url(),
            result_backend: default_result_backend(),
        }
    }
}

/// 默认管理员组
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AdminSettings {
    #[serde(default = "default_admin_username")]
    pub username: String,
    #[serde(default = "default_admin_password")]
    pub password: String,
    #[serde(default = "default_admin_nickname")]
    pub nickname: String,
    #[serde(default = "default_admin_email")]
    pub email: String,
    #[serde(default)]
    pub reset_password: bool,
}
fn default_admin_username() -> String {
    d("admin")
}
fn default_admin_password() -> String {
    d("admin123")
}
fn default_admin_nickname() -> String {
    d("系统管理员")
}
fn default_admin_email() -> String {
    d("admin@codebiu.local")
}
impl Default for AdminSettings {
    fn default() -> Self {
        Self {
            username: default_admin_username(),
            password: default_admin_password(),
            nickname: default_admin_nickname(),
            email: default_admin_email(),
            reset_password: false,
        }
    }
}

// ############################# 组注册表(UI 展示顺序即此顺序) #############################

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
        defaults: defaults::<TokenSettings>,
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
        defaults: defaults::<EmailSettings>,
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
        defaults: defaults::<WebSearchSettings>,
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
        defaults: defaults::<FileSystemSettings>,
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
        defaults: defaults::<DBCacheSettings>,
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
        defaults: defaults::<DBVectorSettings>,
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
        defaults: defaults::<DBGraphSettings>,
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
        defaults: defaults::<TasksSettings>,
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
        defaults: defaults::<AdminSettings>,
        validate: |v| validate::<AdminSettings>(v),
    },
];

#[cfg(test)]
mod tests {
    use super::*;

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

    #[test]
    fn 默认值由结构体派生() {
        // 单一事实来源: 默认值 JSON 必须与结构体 Default 一致
        for schema in GROUPS {
            let value = (schema.validate)(&(schema.defaults)()).expect(schema.group);
            // 默认值经校验后应保持不变(无字段丢失)
            let again = (schema.validate)(&value).unwrap();
            assert_eq!(value, again, "组 {} 默认值往返不一致", schema.group);
        }
    }
}
