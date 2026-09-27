//! module-rag —— 知识库 RAG 模块(完整重写自 Python server_py/src/module_rag)
//!
//! 端点组(挂载前缀 /rag, 见 [`router`]):
//! - /projects            项目管理
//! - /project-members     项目成员
//! - /project-depts       项目部门授权
//! - /project-documents   项目文档(上传/解析/下载等)
//! - /project-document-chunks 分块检索与全库重向量化
//! - /user-models         用户-模型绑定
//! - /conversations       对话与消息
//! - /rag-chat            知识库问答(SSE)
//!
//! 降级口径: 文本类文件原生解析+滑动窗口分块, pdf/docx 等二进制格式解析失败回写
//! "文档解析引擎未支持该格式"; 向量化真实调用 embeddings 但向量库引擎未实现 →
//! 分块落 project_document_chunk 关系表; 问答基于会话历史直连 LLM(SSE start 事件注明)。
//!
//! app/main.rs 装配点(本模块只提供函数, 装配由 app 完成):
//! 1. `Router::nest("/rag", module_rag::router())`
//! 2. 启动钩子调 `module_rag::register_permissions()`
//! 3. 建表后调 `module_rag::register_tables()`(注册中心)与 `module_rag::init_task_runners(state)`
//! 4. 调 `module_rag::init_download_grant(state)` 注册 rag 条目下载授权钩子

// 实体/DTO 层(目录与 Python do/ 对齐; do 是 Rust 保留字, 模块名用 do_)
#[path = "do/mod.rs"]
pub mod do_;

pub mod controllers;
pub mod dao;
pub mod perms;
pub mod services;
pub mod tasks;

use axum::Router;
use common::runtime::AppState;

/// 模块路由(由 app 挂载到 /rag 前缀下)
pub fn router() -> Router<AppState> {
    Router::new()
        .nest("/projects", controllers::project::projects_router())
        .nest("/project-members", controllers::project::members_router())
        .nest("/project-depts", controllers::project::depts_router())
        .nest("/project-documents", controllers::document::documents_router())
        .nest(
            "/project-document-chunks",
            controllers::document::chunks_router(),
        )
        .nest("/user-models", controllers::user_model::user_models_router())
        .nest("/conversations", controllers::chat::conversations_router())
        .nest("/rag-chat", controllers::chat::rag_chat_router())
}

/// 注册模块权限声明(启动钩子调用一次, casbin/权限表幂等同步)
pub fn register_permissions() {
    module_authorization::perms::register(&perms::RAG_DEFINE);
}

/// 模块表注册(建表注册中心; app 启动期统一建表前调用)
pub fn register_tables() {
    common::utils::tables::register("project", |s| {
        s.create_table_from_entity(do_::entity::project::Entity)
    });
    common::utils::tables::register("project_dept", |s| {
        s.create_table_from_entity(do_::entity::project_dept::Entity)
    });
    common::utils::tables::register("project_document", |s| {
        s.create_table_from_entity(do_::entity::project_document::Entity)
    });
    common::utils::tables::register("project_document_chunk", |s| {
        s.create_table_from_entity(do_::entity::project_document_chunk::Entity)
    });
    common::utils::tables::register("project_member", |s| {
        s.create_table_from_entity(do_::entity::project_member::Entity)
    });
    common::utils::tables::register("conversation", |s| {
        s.create_table_from_entity(do_::entity::conversation::Entity)
    });
    common::utils::tables::register("chat_message", |s| {
        s.create_table_from_entity(do_::entity::chat_message::Entity)
    });
    common::utils::tables::register("user_model", |s| {
        s.create_table_from_entity(do_::entity::user_model::Entity)
    });
}

/// 注册 rag 本地任务执行器(app 启动期建表后调用一次; 需传入 AppState 供执行器使用)
pub fn init_task_runners(state: AppState) {
    tasks::init_task_runners(state);
}

/// 注册 rag 业务条目的文件下载授权钩子(app 启动期调用一次)
pub fn init_download_grant(state: AppState) {
    services::permission::register_download_grant(state);
}
