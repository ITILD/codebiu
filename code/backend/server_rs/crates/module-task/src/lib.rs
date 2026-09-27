//! module-task —— 任务队列模块(对齐 Python module_task)
//!
//! 通用任务队列: 类型注册表 + 双引擎派发(local 进程内协程 / celery 未实现) + worker 自愈轮询。
//! 路由挂载在 /task 前缀(由 app 主入口 nest): /task/tasks/{registry,stats,list,{id},...}。
//!
//! 执行器 IoC: 本 crate 不依赖业务模块, rag/agent 等经 register_local_runner 注入本地执行器;
//! worker 轮询经 start_worker 启动(app 启动期调用一次)。

pub mod controllers;
pub mod dao;
pub mod perms;
pub mod services;
pub mod tasks;

// 请求/响应类型层(目录与 Python do/ 对齐; do 是 Rust 保留字, 模块名用 do_)
#[path = "do/mod.rs"]
pub mod do_;

use axum::Router;
use common::runtime::AppState;

pub use tasks::{register_local_runner, registered_task_types, LocalTaskRunner};

/// 模块路由(由 app 主入口 nest 到 /task 前缀, 对齐 Python app.mount("/task") + prefix="/tasks")
pub fn router() -> Router<AppState> {
    Router::new().nest("/tasks", controllers::task::router())
}

/// task 域权限声明注册(task:queue:{read,create,update,delete}; 启动期调用一次)
pub fn register_permissions() {
    perms::register_task_define();
}

/// 模块表注册(建表注册中心; app 启动期统一建表前调用)
pub fn register_tables() {
    common::utils::tables::register("task_queue", |s| {
        s.create_table_from_entity(do_::entity::task_queue::Entity)
    });
}

/// 启动任务 worker 轮询(app 启动期调用一次; 内部 tokio::spawn 后台循环, 本函数立即返回)
pub async fn start_worker(state: AppState) {
    tasks::start_worker(state).await;
}
