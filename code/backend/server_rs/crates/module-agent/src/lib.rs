//! module-agent —— 智能体模块(对齐 Python module_agent)
//!
//! 路由挂载前缀 /agent(由 app 装配):
//! - /agents : 智能体管理 CRUD + 工作流保存 + 运行/运行历史
//! - /agent-chat : 流式对话(SSE)
//! - /conversations : 我的智能体会话列表
//!
//! 分层(对齐 Python 项目): controllers(薄控制器) → services(业务规则) → dao(数据库读写),
//! 请求/响应类型在 do/ 层(与 Python do/*.py 对齐)。
//!
//! 行为偏差说明: Python 的 checkpoints 系列表由 langgraph checkpointer 运行时管理,
//! Rust 侧对话历史改用 chat_message 表(最近 N 条), 故不再注册这些表。

pub mod controllers;
pub mod dao;
pub mod perms;
pub mod seed;
pub mod services;

// 请求/响应类型层(目录与 Python do/ 对齐; do 是 Rust 保留字, 模块名用 do_)
#[path = "do/mod.rs"]
pub mod do_;

use axum::Router;

/// 模块路由(挂载前缀 /agent, 对齐 Python module_app.include_router)
pub fn router() -> Router<common::runtime::AppState> {
    Router::new()
        // 管理与运行控制器共用 /agents 前缀(对齐 Python 两个 controller 同前缀挂载)
        .nest(
            "/agents",
            controllers::agent::router().merge(controllers::agent_run::router()),
        )
        .nest("/agent-chat", controllers::agent_chat::router())
        .nest("/conversations", controllers::agent_conversation::router())
}

/// 基础权限声明(agent 域): 启动期注册(对齐 Python module_permissions.py)
pub fn register_permissions() {
    perms::register_agent_define();
}

/// 模块表注册(建表注册中心; app 启动期统一建表前调用)
///
/// 仅注册 agent/agent_run 两表; checkpoints 系列为 langgraph checkpointer 运行时结构,
/// Rust 侧不使用, 不注册(对话历史持久化在 chat_message 表)。
pub fn register_tables() {
    common::utils::tables::register("agent", |s| {
        s.create_table_from_entity(do_::entity::agent::Entity)
    });
    common::utils::tables::register("agent_run", |s| {
        s.create_table_from_entity(do_::entity::agent_run::Entity)
    });
}

/// 模块启动初始化钩子(表结构就绪后由 app 装配调用): 内置公共智能体幂等种子
pub async fn init_hooks(state: &common::runtime::AppState) {
    services::agent::seed_builtin_agents(state).await;
}
