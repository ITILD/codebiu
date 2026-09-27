//! 主机状态控制器(对齐 Python controller/status.py; 前缀 /server-status, 无鉴权)

use axum::extract::State;
use axum::routing::get;
use axum::{Json, Router};

use common::runtime::AppState;

use crate::do_::status::{HardwareStatus, NetworkStatus, StatusServer};
use crate::services::status as svc;

/// GET /cache —— 获取主机综合状态(60 秒缓存版本, 避免频繁采集)
async fn status_cache(State(state): State<AppState>) -> Json<StatusServer> {
    Json(svc::service().status_cache(&state.http).await)
}

/// GET /sys-info —— 获取主机型号(平台/架构)
async fn sys_info() -> Json<String> {
    Json(svc::sys_info())
}

/// GET /hardware-status —— 获取硬件状态(CPU/内存/磁盘/GPU)
async fn hardware_status() -> Json<HardwareStatus> {
    Json(svc::hardware_status().await)
}

/// GET /network-status —— 获取网络连通状态(并发探测常用站点)
async fn network_status(State(state): State<AppState>) -> Json<Vec<NetworkStatus>> {
    Json(svc::network_status(&state.http).await)
}

/// GET /mount-count —— 查看 app 静态资源挂载路径(调试模块挂载情况)
async fn mount_count() -> Json<Vec<String>> {
    // axum 静态资源挂载固定为此两项(对齐 Python 列出 Mount 路由的调试语义)
    Json(vec!["/static".to_string(), "/common".to_string()])
}

/// 主机状态子路由(nest 到 /server-status 前缀)
pub fn router() -> Router<AppState> {
    Router::new()
        .route("/cache", get(status_cache))
        .route("/sys-info", get(sys_info))
        .route("/hardware-status", get(hardware_status))
        .route("/network-status", get(network_status))
        .route("/mount-count", get(mount_count))
}
