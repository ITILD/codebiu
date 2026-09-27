//! module-ai —— AI 能力模块(对齐 Python module_ai)
//!
//! 路由挂载前缀 /ai(由 app 装配):
//! /model-configs /llm /ocr /voice /rerank /static + GET / 静态首页。
//!
//! 降级约定: 本地 OCR/版面分析与语音引擎(asr/tts/vad/denoise)未在 Rust 服务实现,
//! 对应端点返回业务错误提示; 在线方案(DashScope OCR/rerank/LLM)完整实现。

pub mod controllers;
pub mod dao;
pub mod perms;
pub mod services;
pub mod utils;

// 请求/响应类型层(目录与 Python do/ 对齐; do 是 Rust 保留字, 模块名用 do_)
#[path = "do/mod.rs"]
pub mod do_;

use axum::routing::get;
use axum::Router;
use tower_http::services::ServeDir;

use controllers::static_files;

/// 模块路由(挂载前缀 /ai, 对齐 Python module_app.include_router)
pub fn router() -> Router<common::runtime::AppState> {
    let public = static_files::public_dir();
    Router::new()
        .nest("/model-configs", controllers::model_config::router())
        .nest("/llm", controllers::llm::router())
        .nest("/ocr", controllers::ocr::router())
        .nest("/voice", controllers::voice::router())
        .nest("/rerank", controllers::rerank::router())
        // 首页与静态资源(html=True: 目录索引回退 index.html)
        .route("/", get(static_files::index))
        .nest_service("/static", ServeDir::new(public.join("ai")))
}

/// 基础权限声明(ai 域): 启动期注册(对齐 Python module_permissions.py)
pub fn register_permissions() {
    perms::register_ai_define();
}

/// 模块表注册(建表注册中心; app 启动期统一建表前调用)
pub fn register_tables() {
    common::utils::tables::register("model_config", |s| {
        s.create_table_from_entity(do_::entity::model_config::Entity)
    });
}

/// 模块启动初始化钩子(表结构就绪后由 app 装配调用):
/// 语音模型 server_type 归一化迁移 → default_models 补种
pub async fn init_hooks(state: &common::runtime::AppState) {
    services::model_config::init_hooks(state).await;
}
