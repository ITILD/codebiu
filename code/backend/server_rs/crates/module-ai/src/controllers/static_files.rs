//! AI 模块静态资源(对齐 Python controller/static.py: GET / 返回 public/ai/index.html)

use axum::response::Html;

use common::utils::error::AppError;

/// public 静态目录(config.dir.public, 相对工作目录)
pub fn public_dir() -> std::path::PathBuf {
    std::path::PathBuf::from(&common::config::get().dir.public)
}

/// GET / —— 返回 AI 模块静态首页 HTML
pub async fn index() -> Result<Html<String>, AppError> {
    let path = public_dir().join("ai").join("index.html");
    let html = std::fs::read_to_string(&path)
        .map_err(|e| AppError::Internal(format!("读取首页文件失败: {e}")))?;
    Ok(Html(html))
}
