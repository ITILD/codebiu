//! 字典类型控制器(对齐 Python controller/dict_type.py; 前缀 /dict_types, 无鉴权)

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::routing::{get, post};
use axum::{Json, Router};
use serde::Deserialize;

use common::utils::extract::{AppJson, AppQuery};
use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::pagination::{
    InfiniteScrollParams, InfiniteScrollResponse, PaginationParams, PaginationResponse,
};
use crate::do_::entity::dict_type;

use crate::do_::dict_type::{DictTypeCreate, DictTypeUpdate};
use crate::services::dict_type as svc;

/// POST "" —— 创建字典类型(201; 响应体为 JSON 字符串 id)
pub async fn create_dict_type(
    State(state): State<AppState>,
    AppJson(data): AppJson<DictTypeCreate>,
) -> Result<(StatusCode, Json<String>), AppError> {
    let id = svc::add(&state.db, data).await?;
    Ok((StatusCode::CREATED, Json(id)))
}

/// GET /scroll —— 无限滚动加载字典类型
pub async fn infinite_scroll(
    State(state): State<AppState>,
    AppQuery(params): AppQuery<InfiniteScrollParams>,
) -> Result<Json<InfiniteScrollResponse<dict_type::Model>>, AppError> {
    Ok(Json(svc::get_scroll(&state.db, &params).await?))
}

/// GET /list 查询参数
#[derive(Debug, Deserialize)]
pub struct DictTypeListQuery {
    /// 类型名称/编码模糊搜索(最长 100)
    #[serde(default)]
    pub keyword: Option<String>,
    /// 状态过滤(true=启用/false=禁用)
    #[serde(default)]
    pub is_active: Option<bool>,
}

/// GET /list —— 分页查询字典类型列表(多字段过滤)
pub async fn list_dict_types(
    State(state): State<AppState>,
    AppQuery(pagination): AppQuery<PaginationParams>,
    AppQuery(query): AppQuery<DictTypeListQuery>,
) -> Result<Json<PaginationResponse<dict_type::Model>>, AppError> {
    pagination.validate()?;
    Ok(Json(
        svc::list_paged(&state.db, &pagination, query.keyword.as_deref(), query.is_active).await?,
    ))
}

/// GET /code/{type_code} —— 根据编码获取字典类型(不存在 404)
pub async fn get_dict_type_by_code(
    State(state): State<AppState>,
    Path(type_code): Path<String>,
) -> Result<Json<dict_type::Model>, AppError> {
    let result = svc::get_by_code(&state.db, &type_code).await;
    result
        .ok_or_else(|| AppError::not_found("字典类型不存在"))
        .map(Json)
}

/// GET /{dict_type_id} —— 获取单个字典类型(不存在 404)
pub async fn get_dict_type(
    State(state): State<AppState>,
    Path(dict_type_id): Path<String>,
) -> Result<Json<dict_type::Model>, AppError> {
    let result = svc::get(&state.db, &dict_type_id).await;
    result
        .ok_or_else(|| AppError::not_found("字典类型不存在"))
        .map(Json)
}

/// DELETE /{dict_type_id} —— 删除字典类型(204; 不存在 404)
pub async fn delete_dict_type(
    State(state): State<AppState>,
    Path(dict_type_id): Path<String>,
) -> Result<StatusCode, AppError> {
    svc::delete(&state.db, &dict_type_id).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// PUT /{dict_type_id} —— 更新字典类型(204; 仅显式传入的字段生效; 不存在 404)
pub async fn update_dict_type(
    State(state): State<AppState>,
    Path(dict_type_id): Path<String>,
    AppJson(data): AppJson<DictTypeUpdate>,
) -> Result<StatusCode, AppError> {
    svc::update(&state.db, &dict_type_id, data).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// 字典类型子路由(nest 到 /dict_types 前缀)
pub fn router() -> Router<AppState> {
    Router::new()
        .route("/", post(create_dict_type))
        .route("/scroll", get(infinite_scroll))
        .route("/list", get(list_dict_types))
        .route("/code/{type_code}", get(get_dict_type_by_code))
        .route("/{dict_type_id}", get(get_dict_type).delete(delete_dict_type).put(update_dict_type))
}
