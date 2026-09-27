//! 全局应用状态(对应 Python 侧依赖注入容器的角色)
//!
//! 持有: 数据库连接池 / 静态配置快照 / 访问令牌黑名单 / 全局 HTTP 客户端。
//! 通过 axum `State<AppState>` 注入到各模块 handler。

use crate::config::Config;
use sea_orm::DatabaseConnection;
use std::time::Duration;

/// 访问令牌黑名单(登出即时失效)
///
/// 值为条目自身的过期时间戳(秒); TTL 由登出时按当前动态配置的令牌有效期传入,
/// 惰性过期判断, 缓存层 30 天兜底清理。语义与 Python 侧 Redis 黑名单一致。
pub struct TokenBlacklist {
    inner: moka::sync::Cache<String, i64>,
}

impl TokenBlacklist {
    /// 创建黑名单(缓存层兜底 TTL, 实际失效时间以 revoke 传入为准)
    pub fn new() -> Self {
        Self {
            inner: moka::sync::Cache::builder()
                .time_to_live(Duration::from_secs(30 * 24 * 3600))
                .max_capacity(100_000)
                .build(),
        }
    }

    /// 加入黑名单(expires_in_secs: 令牌剩余有效秒数)
    pub fn revoke(&self, token: &str, expires_in_secs: i64) {
        let expiry = chrono::Utc::now().timestamp() + expires_in_secs;
        self.inner.insert(token.to_string(), expiry);
    }

    /// 是否已被吊销(未过期才算)
    pub fn is_revoked(&self, token: &str) -> bool {
        self.inner
            .get(token)
            .map(|expiry| chrono::Utc::now().timestamp() < expiry)
            .unwrap_or(false)
    }
}

/// 全局应用状态
#[derive(Clone)]
pub struct AppState {
    /// 关系型数据库连接池(sea-orm)
    pub db: DatabaseConnection,
    /// 静态配置快照(启动期加载, 运行期只读)
    pub config: &'static Config,
    /// 访问令牌黑名单
    pub token_blacklist: std::sync::Arc<TokenBlacklist>,
    /// 动态配置中心(TTL 缓存, 运行期可热更新)
    pub settings: std::sync::Arc<crate::config::dynamic::SettingsService>,
    /// 全局 HTTP 客户端(LLM 调用/网页搜索等出网复用)
    pub http: reqwest::Client,
}

impl AppState {
    /// 构建应用状态(数据库连接失败立即报错终止启动)
    pub async fn new(config: &'static Config) -> Result<Self, sea_orm::DbErr> {
        let db = sea_orm::Database::connect(config.db_url()).await?;
        let blacklist = TokenBlacklist::new();
        let http = reqwest::Client::builder()
            .timeout(Duration::from_secs(60))
            .build()
            .expect("HTTP 客户端构建失败");
        Ok(Self {
            db: db.clone(),
            config,
            token_blacklist: std::sync::Arc::new(blacklist),
            settings: crate::config::dynamic::SettingsService::new(db),
            http,
        })
    }
}
