//! module-rag 请求/响应类型层(目录与 Python do/ 对齐; do 是 Rust 保留字, 模块名用 do_)
//!
//! entity/ 为表模型(sea-orm 实体), 其余文件为 API 请求/响应 DTO 与业务常量。

pub mod chat;
pub mod document;
pub mod project;
pub mod prompts;
pub mod user_model;

pub mod entity;
