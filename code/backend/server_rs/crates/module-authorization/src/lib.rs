//! module-authorization —— 授权模块(对齐 Python module_authorization)
//!
//! 路由前缀 /authorization: /auth /users /roles /depts /permissions /casbin-rules /tokens
//!
//! 分层(对齐 Python 项目): controllers(薄控制器) → services(业务规则) → dao(数据库读写),
//! 请求/响应类型在 do/ 层(与 Python do/*.py 对齐)。

pub mod bootstrap;
pub mod casbin_mgr;
pub mod controllers;
pub mod dao;
pub mod deps;
pub mod perms;
pub mod services;
pub mod sys_define;

// 请求/响应类型层(目录与 Python do/ 对齐; do 是 Rust 保留字, 模块名用 do_)
#[path = "do/mod.rs"]
pub mod do_;

use axum::Router;

/// 模块路由(各控制器按 Python include_router 前缀 nest; 子应用下可安全复用 "/" 路径)
pub fn router() -> Router<common::runtime::AppState> {
    Router::new()
        .nest("/auth", controllers::auth::router())
        .nest("/users", controllers::user::router())
        .nest("/roles", controllers::role::router())
        .nest("/depts", controllers::dept::router())
        .nest("/permissions", controllers::permission::router())
        .nest("/casbin-rules", controllers::casbin_rule::router())
        .nest("/tokens", controllers::token::router())
}

/// 基础权限声明(sys 域): 模块导入期注册(对齐 Python module_permissions.py)
pub fn register_permissions() {
    sys_define::register_sys_define();
}

/// 模块表注册(建表注册中心; app 启动期统一建表前调用)
pub fn register_tables() {
    common::utils::tables::register("user", |s| s.create_table_from_entity(do_::entity::user::Entity));
    common::utils::tables::register("role", |s| s.create_table_from_entity(do_::entity::role::Entity));
    common::utils::tables::register("dept", |s| s.create_table_from_entity(do_::entity::dept::Entity));
    common::utils::tables::register("permission", |s| {
        s.create_table_from_entity(do_::entity::permission::Entity)
    });
    common::utils::tables::register("token", |s| s.create_table_from_entity(do_::entity::token::Entity));
    common::utils::tables::register("casbin_rule", |s| {
        s.create_table_from_entity(do_::entity::casbin_rule::Entity)
    });
}
