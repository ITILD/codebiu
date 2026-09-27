//! module-file —— 文件模块(对齐 Python module_file)
//!
//! 虚拟文件系统 + 多存储(local/s3/rustfs)上传下载, 路由挂载在 /file 前缀:
//! /file/filesystem  文件管理全量端点(浏览/上传/分片/秒传/移动/复制/搜索/统计/迁移)
//!
//! 分层(对齐 Python 项目): controllers(薄控制器) → services(业务规则) → dao(数据库读写),
//! 请求/响应类型在 do/ 层; 多存储实现位于 utils/storage(对齐 Python utils/multi_storage)。
//!
//! 头像端点(/authorization/auth/me/avatar)在 Python 侧位于 module_authorization,
//! 因 Rust crate 依赖方向(本模块 → module-authorization)移到本模块实现,
//! 由 app 主入口以相同前缀挂载(controllers::avatar), 前端契约零改动。

pub mod config;
pub mod controllers;
pub mod dao;
pub mod services;
pub mod utils;

// 请求/响应类型层(目录与 Python do/ 对齐; do 是 Rust 保留字, 模块名用 do_)
#[path = "do/mod.rs"]
pub mod do_;

use axum::Router;
use common::runtime::AppState;

/// 模块路由(nest 到 /file 前缀, 对齐 Python app.mount("/file", module_app))
pub fn router() -> Router<AppState> {
    Router::new().nest("/filesystem", controllers::filesystem::router())
}

/// 头像路由(由 app 主入口 nest 到 /authorization 前缀)
///
/// 对应 Python module_authorization/controller/auth.py 的 /me/avatar 两端点:
/// POST /authorization/auth/me/avatar  上传当前用户头像
/// DELETE /authorization/auth/me/avatar  删除当前头像还原默认
pub fn avatar_router() -> Router<AppState> {
    controllers::avatar::router()
}

/// 模块表注册(建表注册中心; app 启动期统一建表前调用)
pub fn register_tables() {
    common::utils::tables::register("file_entry", |s| {
        s.create_table_from_entity(do_::entity::file_entry::Entity)
    });
    common::utils::tables::register("file_content", |s| {
        s.create_table_from_entity(do_::entity::file_content::Entity)
    });
}
