//! module-site —— 个人小站模块(对齐 Python module_site)
//!
//! 路由挂载在 /site 前缀(与 Python app.mount("/site", ...) 一致):
//! /site/blog/posts  博客文章(markdown/url 发布 + 管理 + 展示)
//! /site/todolists   备忘(编辑管理 + 日历展示)
//! /site/ledger/records  记账(收支记录 + 统计)

pub mod controllers;
pub mod perms;

// 请求/响应类型层(目录与 Python do/ 对齐; do 是 Rust 保留字, 模块名用 do_)
#[path = "do/mod.rs"]
pub mod do_;
// 数据访问层(对齐 Python dao/)
pub mod dao;
// 业务逻辑层(对齐 Python service/)
pub mod services;

use axum::Router;

/// 模块路由(nest 到 /site 前缀)
pub fn router() -> Router<common::runtime::AppState> {
    Router::new()
        .nest("/blog/posts", controllers::blog::router())
        .nest("/todolists", controllers::todolist::router())
        .nest("/ledger/records", controllers::ledger::router())
}

/// 权限声明(site 域): 启动期注册(对齐 Python config/permissions.py)
pub fn register_permissions() {
    perms::register_site_define();
}

/// 模块表注册(建表注册中心; app 启动期统一建表前调用)
pub fn register_tables() {
    common::utils::tables::register("blog_post", |s| {
        s.create_table_from_entity(do_::entity::blog_post::Entity)
    });
    common::utils::tables::register("todo_list", |s| {
        s.create_table_from_entity(do_::entity::todo_list::Entity)
    });
    common::utils::tables::register("ledger_record", |s| {
        s.create_table_from_entity(do_::entity::ledger_record::Entity)
    });
}
