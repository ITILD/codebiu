//! 网页搜索模块(对齐 Python src/module_websearch)
//!
//! 提供多引擎网页搜索聚合: DuckDuckGo(免 Key 直连)/Tavily/Firecrawl(需 API Key),
//! 挂载于 /websearch 子应用; 动态配置取自 sys_config 表 websearch 组。

pub mod controllers;
#[path = "do/mod.rs"]
pub mod do_;
pub mod services;
pub mod utils;

use axum::Router;

use common::runtime::AppState;

/// 模块总路由(挂载到 /websearch, 对齐 Python app.mount("/websearch", ...))
pub fn router() -> Router<AppState> {
    controllers::websearch::router()
}
