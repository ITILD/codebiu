//! dev_tools —— 开发辅助模块(对齐 Python module_dev_tools)
//!
//! 路由挂载在 /dev-tools 前缀(与 Python app.mount("/dev-tools", ...) 一致):
//! /dev-tools/template-strings  string.Template 模板字符串管理(创建/分页/滚动/详情/删除/更新/渲染/校验)

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

/// 模块路由(nest 到 /dev-tools 前缀)
pub fn router() -> Router<common::runtime::AppState> {
    Router::new().nest("/template-strings", controllers::template_string::router())
}

/// 权限声明(dev_tools 域): 启动期注册
pub fn register_permissions() {
    perms::register_dev_tools_define();
}

/// 模块表注册(建表注册中心; app 启动期统一建表前调用)
pub fn register_tables() {
    common::utils::tables::register("template_string", |s| {
        s.create_table_from_entity(do_::entity::template_string::Entity)
    });
}
