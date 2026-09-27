//! 字典项控制器(对齐 Python controller/dict_item.py; 前缀 /dict_items, 无鉴权)

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::routing::{get, post};
use axum::{Json, Router};

use common::utils::extract::{AppJson, AppQuery};
use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::pagination::{
    InfiniteScrollParams, InfiniteScrollResponse, PaginationParams, PaginationResponse,
};
use crate::do_::entity::dict_item;

use crate::do_::dict_item::{DictItemCreate, DictItemUpdate};
use crate::services::dict_item as svc;

/// POST "" —— 创建字典项(201; 响应体为 JSON 字符串 id)
pub async fn create_dict_item(
    State(state): State<AppState>,
    AppJson(data): AppJson<DictItemCreate>,
) -> Result<(StatusCode, Json<String>), AppError> {
    let id = svc::add(&state.db, data).await?;
    Ok((StatusCode::CREATED, Json(id)))
}

/// GET /scroll —— 无限滚动加载字典项
pub async fn infinite_scroll(
    State(state): State<AppState>,
    AppQuery(params): AppQuery<InfiniteScrollParams>,
) -> Result<Json<InfiniteScrollResponse<dict_item::Model>>, AppError> {
    Ok(Json(svc::get_scroll(&state.db, &params).await?))
}

/// GET /list —— 分页查询字典项列表(无过滤, total 为全表总数)
pub async fn list_dict_items(
    State(state): State<AppState>,
    AppQuery(pagination): AppQuery<PaginationParams>,
) -> Result<Json<PaginationResponse<dict_item::Model>>, AppError> {
    pagination.validate()?;
    Ok(Json(svc::list_paged(&state.db, &pagination).await?))
}

/// GET /by-type/{type_code} —— 根据字典类型编码查询字典项列表(类型不存在返回空列表)
pub async fn list_dict_items_by_type(
    State(state): State<AppState>,
    Path(type_code): Path<String>,
) -> Result<Json<Vec<dict_item::Model>>, AppError> {
    Ok(Json(svc::list_by_dict_type(&state.db, &type_code).await?))
}

/// GET /by-type/{type_code}/count —— 根据字典类型统计字典项数量(类型不存在返回 0)
pub async fn count_dict_items_by_type(
    State(state): State<AppState>,
    Path(type_code): Path<String>,
) -> Result<Json<i64>, AppError> {
    Ok(Json(svc::count_by_dict_type(&state.db, &type_code).await?))
}

/// GET /code/{item_code} —— 根据编码获取字典项(不存在 404)
pub async fn get_dict_item_by_code(
    State(state): State<AppState>,
    Path(item_code): Path<String>,
) -> Result<Json<dict_item::Model>, AppError> {
    let result = svc::get_by_code(&state.db, &item_code).await;
    result
        .ok_or_else(|| AppError::not_found("字典项不存在"))
        .map(Json)
}

/// GET /{dict_item_id} —— 获取单个字典项(不存在 404)
pub async fn get_dict_item(
    State(state): State<AppState>,
    Path(dict_item_id): Path<String>,
) -> Result<Json<dict_item::Model>, AppError> {
    let result = svc::get(&state.db, &dict_item_id).await;
    result
        .ok_or_else(|| AppError::not_found("字典项不存在"))
        .map(Json)
}

/// DELETE /{dict_item_id} —— 删除字典项(204; 不存在 404)
pub async fn delete_dict_item(
    State(state): State<AppState>,
    Path(dict_item_id): Path<String>,
) -> Result<StatusCode, AppError> {
    svc::delete(&state.db, &dict_item_id).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// PUT /{dict_item_id} —— 更新字典项(204; 仅显式传入的字段生效; 不存在 404)
pub async fn update_dict_item(
    State(state): State<AppState>,
    Path(dict_item_id): Path<String>,
    AppJson(data): AppJson<DictItemUpdate>,
) -> Result<StatusCode, AppError> {
    svc::update(&state.db, &dict_item_id, data).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// 字典项子路由(nest 到 /dict_items 前缀)
pub fn router() -> Router<AppState> {
    Router::new()
        .route("/", post(create_dict_item))
        .route("/scroll", get(infinite_scroll))
        .route("/list", get(list_dict_items))
        .route("/by-type/{type_code}", get(list_dict_items_by_type))
        .route("/by-type/{type_code}/count", get(count_dict_items_by_type))
        .route("/code/{item_code}", get(get_dict_item_by_code))
        .route("/{dict_item_id}", get(get_dict_item).delete(delete_dict_item).put(update_dict_item))
}
