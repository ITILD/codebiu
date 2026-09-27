//! template —— 基础模板模块(对齐 Python module_template)
//!
//! 路由挂载在 /template 前缀(与 Python app.mount("/template", ...) 一致):
//! /template/templates          模板 CRUD + 分页 + 无限滚动 + 批量删除
//! /template/template-ex        扩展示例(multipart 上传 / SSE 流式 / WebSocket 聊天室)
//! /template/template-async-learn  异步并发示例(阻塞线程池/await 挂起/反例/线程池)
//! /template/static             静态页(public/template 目录, 与 Python StaticFiles 一致, 不做鉴权)

pub mod controllers;
pub mod perms;

// 请求/响应类型层(目录与 Python do/ 对齐; do 是 Rust 保留字, 模块名用 do_)
#[path = "do/mod.rs"]
pub mod do_;
// 数据访问层(对齐 Python dao/)
pub mod dao;
// 业务逻辑层(对齐 Python service/)
pub mod services;

use std::path::PathBuf;

use axum::Router;
use tower_http::services::ServeDir;

/// 模块路由(nest 到 /template 前缀)
pub fn router() -> Router<common::runtime::AppState> {
    Router::new()
        .nest("/templates", controllers::template::router())
        .nest("/template-ex", controllers::template_ex::router())
        .nest("/template-async-learn", controllers::async_learn::router())
        // 静态目录(html=True 等价: 目录请求回退 index.html)
        .nest_service("/static", ServeDir::new(template_public_dir()))
}

/// 模板静态目录(对齐 Python DIR_PUBLIC / "template")
pub fn template_public_dir() -> PathBuf {
    PathBuf::from(&common::config::get().dir.public).join("template")
}

/// 权限声明(template 域): 启动期注册
pub fn register_permissions() {
    perms::register_template_define();
}

/// 模块表注册(建表注册中心; app 启动期统一建表前调用)
pub fn register_tables() {
    common::utils::tables::register("template", |s| {
        s.create_table_from_entity(do_::entity::template::Entity)
    });
    common::utils::tables::register("testrelbase", |s| {
        s.create_table_from_entity(do_::entity::testrelbase::Entity)
    });
}
