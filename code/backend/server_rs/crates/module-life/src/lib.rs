//! module-life —— 生活工具模块(对齐 Python module_life)
//!
//! 路由挂载在 /life 前缀(与 Python app.mount("/life", ...) 一致):
//! /life/baby-names  宝宝取名(参考体系严格推算 + AI 流式起名 + 名字管理)

pub mod controllers;
pub mod perms;
pub mod utils;

// 请求/响应类型层(目录与 Python do/ 对齐; do 是 Rust 保留字, 模块名用 do_)
#[path = "do/mod.rs"]
pub mod do_;
// 数据访问层(对齐 Python dao/)
pub mod dao;
// 业务逻辑层(对齐 Python service/)
pub mod services;

use axum::Router;

/// 模块路由(nest 到 /life 前缀)
pub fn router() -> Router<common::runtime::AppState> {
    Router::new().nest("/baby-names", controllers::baby_name::router())
}

/// 权限声明(life 域): 启动期注册(对齐 Python config/permissions.py)
pub fn register_permissions() {
    perms::register_life_define();
}

/// 模块表注册(建表注册中心; app 启动期统一建表前调用)
pub fn register_tables() {
    common::utils::tables::register("baby_name", |s| {
        s.create_table_from_entity(do_::entity::baby_name::Entity)
    });
}
