//! 重排序控制器(对齐 Python controller/rerank.py; 前缀 /rerank)

use axum::extract::State;
use axum::routing::post;
use axum::{Json, Router};

use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::extract::AppJson;

use crate::do_::rerank::{RerankRequest, RerankResponse};
use crate::services::rerank as svc;

/// POST "" —— 执行重排序(返回按相关性降序的 [{node, relevance_score}])
pub async fn rerank(
    State(state): State<AppState>,
    AppJson(req): AppJson<RerankRequest>,
) -> Result<Json<RerankResponse>, AppError> {
    Ok(Json(svc::rerank(&state.db, &state.http, req).await?))
}

/// 重排序子路由(nest 到 /rerank 前缀)
pub fn router() -> Router<AppState> {
    Router::new().route("/", post(rerank))
}
