//! 全局中间件(对齐 Python common/config/server.py 中间件装配)

use axum::body::Body;
use axum::http::{HeaderValue, Request};
use axum::middleware::Next;
use axum::response::Response;
use std::time::Instant;
use tower_http::compression::CompressionLayer;
use tower_http::cors::{Any, CorsLayer};

/// 构建 CORS 层(对齐 Python: allow_origins/*/methods/headers, credentials=False)
pub fn cors_layer() -> CorsLayer {
    CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any)
        // 与 Python CORSMiddleware allow_credentials=False 对齐
        .allow_credentials(false)
        // 预检缓存时长(与常见部署一致)
        .max_age(std::time::Duration::from_secs(600))
}

/// 构建响应压缩层(gzip, 对齐 Python: gzip 中间件)
pub fn compression_layer() -> CompressionLayer {
    CompressionLayer::new().gzip(true)
}

/// X-Process-Time 头注入 + 请求访问日志
pub async fn process_time_middleware(request: Request<Body>, next: Next) -> Response {
    let start = Instant::now();
    let method = request.method().clone();
    let path = request.uri().path().to_string();
    let mut response = next.run(request).await;
    // SSE 流式响应不加压缩与计时(避免缓冲破坏流式语义), 仅普通响应注入
    if !path.contains("/chat") {
        let elapsed = start.elapsed().as_secs_f64();
        if let Ok(value) = HeaderValue::from_str(&format!("{elapsed:.6}")) {
            response.headers_mut().insert("x-process-time", value);
        }
    }
    tracing::debug!("{} {} -> {} ({:.1?})", method, path, response.status(), start.elapsed());
    response
}
