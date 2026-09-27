//! 控制器层(对齐 Python module_file/controller/ + module_authorization 头像端点)
pub mod avatar;
pub mod filesystem;

/// 模块路由(各控制器按 Python include_router 前缀 nest)
use axum::Router;

/// 文件模块路由(挂载于 /file 下, 子前缀 /filesystem 由 lib.rs 组装)
pub fn router() -> Router<common::runtime::AppState> {
    Router::new().nest("/filesystem", filesystem::router())
}

/// 头像路由(契约路径 /authorization/auth/me/avatar, 由 app 挂载到 /authorization 下)
pub fn avatar_router() -> Router<common::runtime::AppState> {
    avatar::router()
}
