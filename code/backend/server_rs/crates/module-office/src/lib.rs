//! module-office —— 文档解析模块(对齐 Python module_office 的 document_parse 部分)
//!
//! 端点(由 app 主入口 nest 到 /office 前缀, 对齐 Python config/server.py 的
//! app.mount("/office", module_app) + include_router(prefix="/document-parse")):
//! - POST /office/document-parse/get-markdown-by-file  上传文件解析为 Markdown
//! - POST /office/document-parse/split-code            Python/Java 代码语义分块
//!
//! 解析器说明(对齐 utils/file_parase/factory.py 的后缀注册表):
//! - 文本类(.md/.markdown/.csv/.txt)与代码(.py/.java)由 Rust 原生实现;
//! - 二进制格式(.pdf/.docx/.doc/.pptx/.xlsx)依赖 docling 引擎, Rust 服务未实现,
//!   统一返回业务错误; 图片/音频/视频按 Python 语义返回空内容。
//!
//! 该模块无 DB 表模型(do/ 仅 DTO), 不注册表; Python 侧无权限码声明,
//! 仅要求登录(对齐 get_current_user_id)。

pub mod controllers;
pub mod services;
pub mod utils;

// 请求/响应类型层(目录与 Python do/ 对齐; do 是 Rust 保留字, 模块名用 do_)
#[path = "do/mod.rs"]
pub mod do_;

use axum::Router;
use common::runtime::AppState;

/// 模块路由(由 app 主入口 nest 到 /office 前缀)
pub fn router() -> Router<AppState> {
    Router::new().nest("/document-parse", controllers::document_parse::router())
}

/// 注册 office 域权限声明(模块无权限码, 空实现保持 main.rs 装配统一)
pub fn register_permissions() {}

/// 模块表注册(无 DB 表, 空实现)
pub fn register_tables() {}
