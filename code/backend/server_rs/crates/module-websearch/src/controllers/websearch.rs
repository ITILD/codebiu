//! 网页搜索控制器(对齐 Python module_websearch/controller/websearch.py)
//!
//! 端点: GET /engines、POST /search; 权限码 main:search:read。
//! 错误契约: 参数/配置类失败 400, 上游引擎请求失败 502, 裸 {"detail": 文案}。

use axum::extract::State;
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};

use common::runtime::AppState;
use common::utils::error::AppError;

use module_authorization::deps::{authorize, AuthUserId};

use crate::do_::websearch::{EngineInfo, SearchRequest, SearchResponse};
use crate::services::websearch::WebSearchService;

/// 网页搜索权限校验(main:search:read)
async fn require_perm(user: &AuthUserId) -> Result<(), AppError> {
    authorize(&user.0, "main", "search", "read").await
}

/// 查询可用搜索引擎列表(默认引擎排前,含是否需要/已配置 API Key)
async fn list_engines(
    State(state): State<AppState>,
    user: AuthUserId,
) -> Result<Response, AppError> {
    require_perm(&user).await?;
    let service = WebSearchService::new();
    let infos: Vec<EngineInfo> = service.list_engines(&state).await?;
    Ok(Json(infos).into_response())
}

/// 网页搜索(默认 DuckDuckGo)
async fn search(
    State(state): State<AppState>,
    user: AuthUserId,
    Json(request): Json<SearchRequest>,
) -> Result<Response, AppError> {
    require_perm(&user).await?;
    // 请求体字段校验(对齐 pydantic: query 1~500 / limit 1~30 / blocked_sites ≤50)
    let query_len = request.query.chars().count();
    if !(1..=500).contains(&query_len) {
        return Err(AppError::validation(
            &["body", "query"],
            "String should have at most 500 characters",
        ));
    }
    if let Some(limit) = request.limit {
        if !(1..=30).contains(&limit) {
            return Err(AppError::validation(
                &["body", "limit"],
                "Input should be between 1 and 30",
            ));
        }
    }
    if request.blocked_sites.len() > 50 {
        return Err(AppError::validation(
            &["body", "blocked_sites"],
            "List should have at most 50 items after validation",
        ));
    }
    let service = WebSearchService::new();
    let resp: SearchResponse = service.search(&state, &request).await?;
    Ok(Json(resp).into_response())
}

/// 模块路由(挂载到 /websearch 下, 对齐 Python module_app.include_router)
pub fn router() -> Router<AppState> {
    Router::new()
        .route("/engines", get(list_engines))
        .route("/search", post(search))
}
