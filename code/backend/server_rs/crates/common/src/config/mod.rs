//! 分层配置加载(语义与 Python 侧 common/config/index.py 逐条对齐)
//!
//! 层级(低 → 高, 后层覆盖前层, 嵌套 dict 深合并, list/标量整体替换):
//!   1. config.yaml        基线层(入 git, 必需, 缺失启动失败)
//!   2. config.seed.yaml   约定种子层(gitignored, 存在即加载, 缺失属正常)
//!   3. APP_ENV 环境层     APP_ENV=dev → config.dev.yaml(缺失告警跳过)
//!   4. CONFIG_PATH 部署层 逗号分隔多文件按序覆盖(显式指定, 缺失即失败)
//!   5. CODEBIU_* 环境变量  键级覆盖最高优先级, 嵌套键用双下划线:
//!                         CODEBIU_TOKEN__SECRET_KEY=xxx → token.secret_key

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::sync::OnceLock;

pub mod dynamic;

// ############################# 常量(与 Python 侧一致) #############################
/// 基线配置文件
pub const BASE_FILE: &str = "config.yaml";
/// 约定种子文件
pub const SEED_FILE: &str = "config.seed.yaml";
/// 环境切换变量
pub const ENV_APP_ENV: &str = "APP_ENV";
/// 部署覆盖层文件环境变量
pub const ENV_LAYER_FILES: &str = "CONFIG_PATH";
/// 键级环境变量前缀
pub const ENV_PREFIX: &str = "CODEBIU";

// ############################# 强类型配置结构 #############################

/// 全局标识
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GlobalSection {
    #[serde(default = "default_app_name")]
    pub name: String,
    #[serde(default)]
    pub version: String,
}

fn default_app_name() -> String {
    "codebiu".to_string()
}

/// 状态配置
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StateSection {
    #[serde(default = "default_true")]
    pub is_dev: bool,
}

fn default_true() -> bool {
    true
}

impl Default for StateSection {
    fn default() -> Self {
        Self { is_dev: default_true() }
    }
}

/// 后端服务配置
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServerSection {
    #[serde(default)]
    pub server_root_path: String,
    #[serde(default = "default_host")]
    pub host: String,
    #[serde(default = "default_port")]
    pub port: u16,
}

fn default_host() -> String {
    "0.0.0.0".to_string()
}

fn default_port() -> u16 {
    2001
}

impl Default for ServerSection {
    fn default() -> Self {
        Self {
            server_root_path: String::new(),
            host: default_host(),
            port: default_port(),
        }
    }
}

/// 中间件配置
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MiddlewareSection {
    #[serde(default = "default_true")]
    pub cors: bool,
    #[serde(default = "default_true")]
    pub gzip: bool,
}

impl Default for MiddlewareSection {
    fn default() -> Self {
        Self { cors: true, gzip: true }
    }
}

/// 子目录定义
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DirChild {
    #[serde(default = "default_child")]
    pub source: String,
    #[serde(default = "default_child")]
    pub upload: String,
    #[serde(default = "default_child")]
    pub log: String,
    #[serde(default = "default_child")]
    pub sys_out: String,
    #[serde(default = "default_child")]
    pub temp: String,
    #[serde(default = "default_child")]
    pub db: String,
    #[serde(default = "default_child")]
    pub test: String,
    #[serde(default = "default_child")]
    pub model: String,
    #[serde(default = "default_child")]
    pub lib_third: String,
}

fn default_child() -> String {
    String::new()
}

impl Default for DirChild {
    fn default() -> Self {
        Self {
            source: "source".into(),
            upload: "upload".into(),
            log: "log".into(),
            sys_out: "sys_out".into(),
            temp: "temp".into(),
            db: "db".into(),
            test: "test".into(),
            model: "model".into(),
            lib_third: "lib_third".into(),
        }
    }
}

/// 目录配置
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DirSection {
    #[serde(default = "default_base")]
    pub base: String,
    #[serde(default)]
    pub base_child: DirChild,
    #[serde(default = "default_public")]
    pub public: String,
}

fn default_base() -> String {
    "temp_source".to_string()
}

fn default_public() -> String {
    "public".to_string()
}

/// 数据库配置(引导级: 动态配置中心本身依赖它)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DbRelSection {
    #[serde(default = "default_db_type")]
    pub r#type: String,
    #[serde(default = "default_db_database")]
    pub database: String,
    /// postgres 专用可选字段
    #[serde(default)]
    pub host: Option<String>,
    #[serde(default)]
    pub port: Option<u16>,
    #[serde(default)]
    pub user: Option<String>,
    #[serde(default)]
    pub password: Option<String>,
}

fn default_db_type() -> String {
    "sqlite".to_string()
}

fn default_db_database() -> String {
    "temp_source/db/data.db".to_string()
}

/// 默认管理员配置
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AdminSection {
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

// ############################# MinerU 文档解析引擎 #############################
// 对齐 Python 侧 mineru 节(module-office 解析 pdf/docx 等二进制格式的默认引擎)

/// MinerU 引擎配置(默认值与 Python 侧 config.yaml 的 mineru 节一致)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MinerUSection {
    /// 部署模式: remote(mineru.net 远程 API, 默认) / local(本地 docker mineru-api)
    #[serde(default = "default_mineru_mode")]
    pub mode: String,
    /// 远程 API token(密钥只放种子层或 CODEBIU_MINERU__TOKEN 环境变量)
    #[serde(default)]
    pub token: String,
    #[serde(default = "default_mineru_remote_url")]
    pub remote_base_url: String,
    /// 本地 docker mineru-api 地址; 端点默认为 2.x 契约 /file_parse
    #[serde(default = "default_mineru_local_url")]
    pub local_base_url: String,
    #[serde(default = "default_mineru_local_endpoint")]
    pub local_endpoint: String,
    /// 解析参数: pipeline / vlm
    #[serde(default = "default_mineru_model")]
    pub model_version: String,
    #[serde(default = "default_mineru_lang")]
    pub language: String,
    /// false 自动判断是否 OCR
    #[serde(default)]
    pub is_ocr: bool,
    #[serde(default = "default_true")]
    pub enable_formula: bool,
    #[serde(default = "default_true")]
    pub enable_table: bool,
    /// 单次 HTTP 请求超时(秒)
    #[serde(default = "default_mineru_timeout")]
    pub timeout: f64,
    /// 远程结果轮询间隔(秒)
    #[serde(default = "default_mineru_poll_interval")]
    pub poll_interval: f64,
    /// 远程任务最长等待(秒)
    #[serde(default = "default_mineru_poll_timeout")]
    pub poll_timeout: f64,
}

fn default_mineru_mode() -> String {
    "remote".to_string()
}

fn default_mineru_remote_url() -> String {
    "https://mineru.net/api/v4".to_string()
}

fn default_mineru_local_url() -> String {
    "http://127.0.0.1:8000".to_string()
}

fn default_mineru_local_endpoint() -> String {
    "/file_parse".to_string()
}

fn default_mineru_model() -> String {
    "pipeline".to_string()
}

fn default_mineru_lang() -> String {
    "ch".to_string()
}

fn default_mineru_timeout() -> f64 {
    300.0
}

fn default_mineru_poll_interval() -> f64 {
    5.0
}

fn default_mineru_poll_timeout() -> f64 {
    1800.0
}

impl Default for MinerUSection {
    fn default() -> Self {
        serde_json::from_value(serde_json::json!({})).expect("MinerU 默认配置构造失败")
    }
}

fn default_admin_username() -> String {
    "admin".to_string()
}

fn default_admin_password() -> String {
    "admin123".to_string()
}

fn default_admin_nickname() -> String {
    "系统管理员".to_string()
}

fn default_admin_email() -> String {
    "admin@codebiu.local".to_string()
}

impl Default for DirSection {
    fn default() -> Self {
        Self {
            base: default_base(),
            base_child: DirChild::default(),
            public: default_public(),
        }
    }
}

impl Default for DbRelSection {
    fn default() -> Self {
        Self {
            r#type: default_db_type(),
            database: default_db_database(),
            host: None,
            port: None,
            user: None,
            password: None,
        }
    }
}

impl Default for AdminSection {
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

/// 顶层配置结构(字段缺失时使用与 config.yaml 一致的默认值)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    #[serde(default = "default_global")]
    pub global: GlobalSection,
    #[serde(default)]
    pub state: StateSection,
    #[serde(default)]
    pub server: ServerSection,
    #[serde(default)]
    pub middleware: MiddlewareSection,
    #[serde(default)]
    pub dir: DirSection,
    #[serde(default)]
    pub db_rel: DbRelSection,
    #[serde(default)]
    pub admin: AdminSection,
    #[serde(default)]
    pub mineru: MinerUSection,
}

fn default_global() -> GlobalSection {
    GlobalSection {
        name: default_app_name(),
        version: "0.0.1".to_string(),
    }
}

impl Default for Config {
    fn default() -> Self {
        serde_json::from_value(serde_json::json!({})).expect("默认配置构造失败")
    }
}

impl Config {
    /// 数据库连接 URL(供 sea-orm 使用)
    ///
    /// - sqlite: `sqlite://路径?mode=rwc`(自动建文件), Windows 反斜杠归一化
    /// - postgres: `postgres://user:pass@host:port/db`
    pub fn db_url(&self) -> String {
        match self.db_rel.r#type.as_str() {
            "postgres" | "postgresql" => {
                let host = self.db_rel.host.as_deref().unwrap_or("127.0.0.1");
                let port = self.db_rel.port.unwrap_or(5432);
                let user = self.db_rel.user.as_deref().unwrap_or("postgres");
                let password = self.db_rel.password.as_deref().unwrap_or("");
                format!("postgres://{user}:{password}@{host}:{port}/{}", self.db_rel.database)
            }
            // sqlite 及其他默认走 sqlite 文件
            _ => {
                let path = self.db_rel.database.replace('\\', "/");
                format!("sqlite://{path}?mode=rwc")
            }
        }
    }
}

// ############################# 加载实现 #############################

/// 递归深合并: 双方均为 Object 时逐键递归, 其余以 overlay 整体覆盖(对齐 Python _deep_merge)
pub fn deep_merge(base: &mut serde_json::Value, overlay: &serde_json::Value) {
    match (base, overlay) {
        (serde_json::Value::Object(b), serde_json::Value::Object(o)) => {
            for (key, value) in o {
                match b.get_mut(key) {
                    // 双方均为对象 → 递归合并
                    Some(slot) if slot.is_object() && value.is_object() => deep_merge(slot, value),
                    // 其余(list/标量/类型变化) → 整体覆盖
                    _ => {
                        b.insert(key.clone(), value.clone());
                    }
                }
            }
        }
        // 非对象合并 → overlay 直接替换
        (slot, overlay) => *slot = overlay.clone(),
    }
}

/// 读取单个 yaml 层(顶层必须是键值映射, 空文件视为空层)
fn read_layer(file: &Path) -> Result<serde_json::Value, String> {
    let content = std::fs::read_to_string(file)
        .map_err(|e| format!("配置文件读取失败 {}: {e}", file.display()))?;
    let yaml: serde_yaml::Value =
        serde_yaml::from_str(&content).map_err(|e| format!("配置文件解析失败 {}: {e}", file.display()))?;
    if !yaml.is_mapping() && !yaml.is_null() {
        return Err(format!("配置文件 {} 顶层必须是键值映射", file.display()));
    }
    // 统一转成 serde_json 便于合并(非字符串键丢弃)
    serde_json::to_value(yaml).map_err(|e| format!("配置转换失败 {}: {e}", file.display()))
}

/// 解析层级文件清单(对齐 Python _resolve_layer_files):
/// 基线必需; 种子/环境层缺失告警跳过; CONFIG_PATH 显式指定缺失即失败
fn resolve_layer_files() -> Result<Vec<PathBuf>, String> {
    let base = PathBuf::from(BASE_FILE);
    if !base.exists() {
        return Err(format!(
            "基线配置文件不存在: {BASE_FILE} (需在 server_rs 目录下启动)"
        ));
    }
    let mut files = vec![base];
    // 约定种子层: 存在即加载
    let seed = PathBuf::from(SEED_FILE);
    if seed.exists() {
        files.push(seed);
    }
    // APP_ENV 环境覆盖层
    let app_env = std::env::var(ENV_APP_ENV).unwrap_or_default().trim().to_string();
    if !app_env.is_empty() {
        let file = PathBuf::from(format!("config.{app_env}.yaml"));
        if file.exists() {
            files.push(file);
        } else {
            tracing::warn!("APP_ENV={app_env} 对应的环境配置 {} 不存在, 已跳过", file.display());
        }
    }
    // CONFIG_PATH 部署覆盖层(逗号分隔, 按序覆盖, 缺失即失败)
    let deploy = std::env::var(ENV_LAYER_FILES).unwrap_or_default();
    for p in deploy.split(',') {
        let p = p.trim();
        if p.is_empty() {
            continue;
        }
        let file = PathBuf::from(p);
        if !file.exists() {
            return Err(format!("配置覆盖层文件不存在: {}", file.display()));
        }
        files.push(file);
    }
    Ok(files)
}

/// 应用 CODEBIU_* 键级环境变量覆盖(双下划线嵌套: CODEBIU_TOKEN__SECRET_KEY → token.secret_key)
///
/// 值先按 YAML 解析(数字/布尔/JSON 结构自动识别), 解析失败按原始字符串处理。
fn apply_env_overrides(merged: &mut serde_json::Value) {
    let mut overrides: BTreeMap<String, String> = BTreeMap::new();
    for (key, value) in std::env::vars() {
        if let Some(rest) = key.strip_prefix(format!("{ENV_PREFIX}_").as_str()) {
            overrides.insert(rest.to_string(), value);
        }
    }
    for (key, raw) in overrides {
        // 双下划线 → 嵌套路径(键名转小写, 与 Dynaconf 默认行为一致)
        let path: Vec<String> = key
            .split("__")
            .map(|seg| seg.to_lowercase())
            .collect();
        let value = serde_yaml::from_str::<serde_yaml::Value>(&raw)
            .ok()
            .and_then(|v| serde_json::to_value(v).ok())
            .unwrap_or(serde_json::Value::String(raw));
        // 逐级下钻创建对象插槽(reborrow 避免移动)
        let mut cursor: &mut serde_json::Value = merged;
        for seg in &path[..path.len() - 1] {
            if !cursor.is_object() {
                *cursor = serde_json::Value::Object(serde_json::Map::new());
            }
            cursor = cursor
                .as_object_mut()
                .expect("已确保为对象")
                .entry(seg.clone())
                .or_insert(serde_json::Value::Object(serde_json::Map::new()));
        }
        if !cursor.is_object() {
            *cursor = serde_json::Value::Object(serde_json::Map::new());
        }
        cursor
            .as_object_mut()
            .expect("已确保为对象")
            .insert(path[path.len() - 1].clone(), value);
    }
}

/// 分层合并 + CODEBIU_* 覆盖(唯一加载路径, load/load_raw 共用)
fn load_merged() -> Result<serde_json::Value, String> {
    // .env 自动加载(真实环境变量优先, 不覆盖)
    let _ = dotenvy::dotenv();
    let mut merged = serde_json::Value::Object(serde_json::Map::new());
    for file in resolve_layer_files()? {
        let layer = read_layer(&file)?;
        deep_merge(&mut merged, &layer);
    }
    apply_env_overrides(&mut merged);
    Ok(merged)
}

/// 强类型配置(结构校验失败即启动失败)
pub fn load() -> Result<Config, String> {
    serde_json::from_value(load_merged()?).map_err(|e| format!("配置结构校验失败: {e}"))
}

/// 全局配置单例(启动时初始化一次; 运行期只读)
static CONFIG: OnceLock<Config> = OnceLock::new();
/// 合并后的原始配置 JSON(动态配置中心首启种子使用, 含 token/email 等未强类型的节)
static RAW_JSON: OnceLock<serde_json::Value> = OnceLock::new();

/// 初始化全局配置单例(进程内只允许一次; 重复调用返回首次结果)
pub fn init() -> Result<&'static Config, String> {
    let cfg = load()?;
    let _ = CONFIG.set(cfg);
    Ok(get())
}

/// 获取全局配置(未初始化时惰性加载)
pub fn get() -> &'static Config {
    CONFIG.get_or_init(|| load().unwrap_or_else(|e| panic!("配置加载失败: {e}")))
}

/// 获取合并后的原始配置 JSON(动态配置中心 seed_from_yaml 读取同名节用)
pub fn raw_json() -> &'static serde_json::Value {
    RAW_JSON.get_or_init(|| load_raw().unwrap_or_else(|e| panic!("配置加载失败: {e}")))
}

/// 仅加载原始合并 JSON(动态配置中心 seed_from_yaml 读取同名节用, 不做强类型校验)
fn load_raw() -> Result<serde_json::Value, String> {
    load_merged()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn 深合并_嵌套dict递归_标量与list整体替换() {
        let mut base = serde_json::json!({
            "server": {"host": "0.0.0.0", "port": 2001},
            "dir": {"base_child": ["a", "b"]},
            "state": {"is_dev": true}
        });
        let overlay = serde_json::json!({
            "server": {"port": 3000},
            "dir": {"base_child": ["c"]},
        });
        deep_merge(&mut base, &overlay);
        assert_eq!(base["server"]["host"], "0.0.0.0");
        assert_eq!(base["server"]["port"], 3000);
        assert_eq!(base["dir"]["base_child"], serde_json::json!(["c"]));
        assert_eq!(base["state"]["is_dev"], true);
    }

    #[test]
    fn 环境变量覆盖_双下划线嵌套() {
        // 构造基线
        let mut merged = serde_json::json!({"token": {"secret_key": "old", "expire_minutes": 30}});
        // 临时注入环境变量(edition 2024 中 set_var 为 unsafe; 测试进程串行执行该用例)
        // SAFETY: 单线程测试环境内临时设置, 用后即清理
        unsafe {
            std::env::set_var("CODEBIU_TOKEN__SECRET_KEY", "new_secret");
            std::env::set_var("CODEBIU_TOKEN__EXPIRE_MINUTES", "60");
        }
        apply_env_overrides(&mut merged);
        assert_eq!(merged["token"]["secret_key"], "new_secret");
        assert_eq!(merged["token"]["expire_minutes"], 60);
        // 清理
        unsafe {
            std::env::remove_var("CODEBIU_TOKEN__SECRET_KEY");
            std::env::remove_var("CODEBIU_TOKEN__EXPIRE_MINUTES");
        }
    }

    #[test]
    fn 默认值兜底_空配置可用() {
        let cfg: Config = serde_json::from_value(serde_json::json!({})).unwrap();
        assert_eq!(cfg.server.port, 2001);
        assert_eq!(cfg.admin.username, "admin");
        assert_eq!(cfg.db_rel.r#type, "sqlite");
    }

    #[test]
    #[allow(non_snake_case)]
    fn 数据库URL_sqlite路径归一化() {
        let cfg: Config = serde_json::from_value(serde_json::json!({
            "db_rel": {"type": "sqlite", "database": "temp_source\\db\\data.db"}
        }))
        .unwrap();
        assert_eq!(cfg.db_url(), "sqlite://temp_source/db/data.db?mode=rwc");
    }
}
