//! 数据库管理控制器(对齐 Python controller/db.py; 前缀 /db, 无鉴权)

use axum::extract::State;
use axum::http::StatusCode;
use axum::routing::get;
use axum::{Json, Router};
use serde::Deserialize;

use common::utils::extract::AppQuery;
use common::runtime::AppState;
use common::utils::error::AppError;

use crate::do_::db::TableMeta;
use crate::services::db_meta;

/// GET /tables 查询参数
#[derive(Debug, Deserialize)]
pub struct TablesQuery {
    /// 按表名/注释关键字过滤
    #[serde(default)]
    pub keyword: Option<String>,
}

/// 成功响应(对齐 FastAPI 返回 HTTPException(200, detail=...) 的序列化行为:
/// HTTP 201 + {"status_code": 200, "detail": {"message": "update table success"}})
fn update_table_response() -> (StatusCode, Json<serde_json::Value>) {
    (
        StatusCode::CREATED,
        Json(serde_json::json!({
            "status_code": 200,
            "detail": { "message": "update table success" }
        })),
    )
}

/// GET /create —— 创建所有未创建的数据库表
async fn create(
    State(state): State<AppState>,
) -> Result<(StatusCode, Json<serde_json::Value>), AppError> {
    db_meta::create_all(&state.db).await?;
    Ok(update_table_response())
}

/// GET /reset —— 重置所有数据库表(先删后建)
async fn reset(
    State(state): State<AppState>,
) -> Result<(StatusCode, Json<serde_json::Value>), AppError> {
    db_meta::drop_all(&state.db).await?;
    db_meta::create_all(&state.db).await?;
    Ok(update_table_response())
}

/// GET /tables —— 数据表清单(数据量/最近更新时间)
async fn tables(
    State(state): State<AppState>,
    AppQuery(q): AppQuery<TablesQuery>,
) -> Result<Json<Vec<TableMeta>>, AppError> {
    Ok(Json(db_meta::tables(&state.db, q.keyword.as_deref()).await?))
}

/// GET /vector —— 向量库表清单(未接入时 type 为 null)
async fn vector_tables() -> Json<serde_json::Value> {
    Json(db_meta::vector_tables().await)
}

/// GET /cache —— 缓存数据库信息(未接入时 type 为 null)
async fn cache_info() -> Json<serde_json::Value> {
    Json(db_meta::cache_info().await)
}

/// GET /graph —— 图数据库信息(未接入时 type 为 null)
async fn graph_info() -> Json<serde_json::Value> {
    Json(db_meta::graph_info().await)
}

/// 数据库管理子路由(nest 到 /db 前缀)
pub fn router() -> Router<AppState> {
    Router::new()
        .route("/create", get(create))
        .route("/reset", get(reset))
        .route("/tables", get(tables))
        .route("/vector", get(vector_tables))
        .route("/cache", get(cache_info))
        .route("/graph", get(graph_info))
}
