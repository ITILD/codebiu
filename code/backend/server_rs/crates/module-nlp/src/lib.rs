//! nlp —— 同义词管理模块(对齐 Python module_nlp)
//!
//! 路由挂载在 /nlp 前缀(与 Python app.mount("/nlp", ...) 一致):
//! /nlp/synonyms  同义词组与同义词的增删改查/批量操作/搜索聚合。
//! 说明: Python 侧 utils/tokenizer/spacy_tokenizer.py 是独立脚本(依赖 spacy 模型),
//! 未暴露任何端点, 故无需等价实现。

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

/// 模块路由(nest 到 /nlp 前缀)
pub fn router() -> Router<common::runtime::AppState> {
    Router::new().nest("/synonyms", controllers::synonym::router())
}

/// 权限声明(nlp 域): 启动期注册
pub fn register_permissions() {
    perms::register_nlp_define();
}

/// 模块表注册(建表注册中心; app 启动期统一建表前调用)
pub fn register_tables() {
    common::utils::tables::register("synonym", |s| {
        s.create_table_from_entity(do_::entity::synonym::Entity)
    });
    common::utils::tables::register("synonym_group", |s| {
        s.create_table_from_entity(do_::entity::synonym_group::Entity)
    });
}
