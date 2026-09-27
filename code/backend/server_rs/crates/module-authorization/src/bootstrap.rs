//! 默认管理员账户引导(对齐 Python config/admin.py)
//!
//! 管理员引导参数来自配置中心 admin 组(首次启动由 yaml 种子, 之后以 DB 为准)。
//! 启动时由 ensure_default_admin 幂等创建/修复管理员账户, 并绑定全局域 "*" 的
//! admin 角色(拥有全部权限)。重复启动安全: 已存在且状态一致时不产生写操作。

use tracing::{error, info, warn};

use crate::casbin_mgr::auth;
use crate::deps::sync_default_user_roles;
use crate::services::user as user_svc;
use common::config::dynamic::AdminSettings;
use common::utils::security::password::{hash_password, verify_password};

/// 幂等创建/修复默认管理员(建表后启动钩子调用, casbin 未初始化时跳过)
pub async fn ensure_default_admin(
    db: &sea_orm::DatabaseConnection,
    settings: &common::config::dynamic::SettingsService,
) {
    let manager = auth();
    if !manager.ready().await {
        warn!("Casbin enforcer 未初始化,跳过默认管理员引导");
        return;
    }
    let cfg: AdminSettings = match settings.get("admin").await {
        Ok(cfg) => cfg,
        Err(e) => {
            error!("读取管理员引导配置失败: {e}");
            return;
        }
    };
    match user_svc::get_by_username(db, &cfg.username).await {
        None => create_admin(db, &cfg).await,
        Some(user) => repair_admin(db, user, &cfg).await,
    }
}

/// 创建默认管理员账户并绑定全局管理员角色
async fn create_admin(db: &sea_orm::DatabaseConnection, cfg: &AdminSettings) {
    let password = match hash_password(&cfg.password) {
        Ok(p) => p,
        Err(e) => {
            error!("管理员密码哈希失败: {e}");
            return;
        }
    };
    let is_first_user = user_svc::count(db).await == 0;
    let created = user_svc::create(
        db,
        crate::do_::user::UserCreate {
            username: cfg.username.clone(),
            password,
            dept_id: None,
            email: Some(cfg.email.clone()),
            phone: None,
            nickname: Some(cfg.nickname.clone()),
            avatar: None,
            is_active: Some(true),
        },
    )
    .await;
    let created = match created {
        Ok(u) => u,
        Err(e) => {
            error!("默认管理员引导失败: {e}");
            return;
        }
    };
    // 绑定角色(首个用户引导逻辑之外, 管理员恒绑定全局 admin)
    bind_admin_role(&created.id).await;
    let _ = sync_default_user_roles(&created.id, is_first_user).await;
    info!("默认管理员 '{}' 已创建并拥有全部权限", cfg.username);
}

/// 修复已存在的管理员账户(角色绑定/禁用状态/密码)
async fn repair_admin(
    db: &sea_orm::DatabaseConnection,
    user: crate::do_::entity::user::Model,
    cfg: &AdminSettings,
) {
    bind_admin_role(&user.id).await;
    let mut updates = crate::do_::user::UserUpdate::default();
    if !user.is_active {
        updates.is_active = Some(true);
    }
    if cfg.reset_password && !verify_password(&cfg.password, &user.password) {
        updates.password = Some(cfg.password.clone());
    }
    if updates.has_any() {
        if let Err(e) = user_svc::update(db, &user.id, updates).await {
            error!("默认管理员修复失败: {e}");
            return;
        }
        info!("默认管理员 '{}' 已修复", cfg.username);
    }
}

/// 绑定全局域 "*" 的 admin 角色(幂等)
async fn bind_admin_role(user_id: &str) {
    let manager = auth();
    if !manager.has_grouping_policy(user_id, "admin", "*").await {
        if let Err(e) = manager
            .add_grouping_policy(vec![user_id.into(), "admin".into(), "*".into()])
            .await
        {
            error!("绑定管理员角色失败: {e}");
        }
    }
}
