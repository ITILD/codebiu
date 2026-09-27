//! module-main —— 系统基础资源模块(对齐 Python module_main)
//!
//! 路由挂载在根路径(与 Python 一致, 无 /main 前缀):
//! /dict_types /dict_items /sys-configs /db /server-status
//! 以及 GET / 首页 + /static /common 静态资源。

pub mod bootstrap;
pub mod controllers;
pub mod dict_seed;
pub mod perms;

// 请求/响应类型层(目录与 Python do/ 对齐; do 是 Rust 保留字, 模块名用 do_)
#[path = "do/mod.rs"]
pub mod do_;
// 数据访问层(对齐 Python dao/)
pub mod dao;
// 业务逻辑层(对齐 Python service/)
pub mod services;

use axum::routing::get;
use axum::Router;
use tower_http::services::ServeDir;

use controllers::static_files;

/// 模块路由(挂载到根路径, 对齐 Python app.include_router / app.mount)
pub fn router() -> Router<common::runtime::AppState> {
    let public = static_files::public_dir();
    Router::new()
        .nest("/dict_types", controllers::dict_type::router())
        .nest("/dict_items", controllers::dict_item::router())
        .nest("/sys-configs", controllers::sys_config::router())
        .nest("/db", controllers::db::router())
        .nest("/server-status", controllers::status::router())
        // 首页与静态资源(html=True: 目录索引回退 index.html)
        .route("/", get(static_files::index))
        .nest_service("/static", ServeDir::new(public.join("main")))
        .nest_service("/common", ServeDir::new(public.join("common")))
}

/// 基础权限声明(main 域): 启动期注册(对齐 Python module_permissions.py)
pub fn register_permissions() {
    perms::register_main_define();
}

/// 模块表注册(建表注册中心; app 启动期统一建表前调用)
pub fn register_tables() {
    common::utils::tables::register("dict_type", |s| {
        s.create_table_from_entity(do_::entity::dict_type::Entity)
    });
    common::utils::tables::register("dict_item", |s| {
        s.create_table_from_entity(do_::entity::dict_item::Entity)
    });
}
