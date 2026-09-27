//! 几何要素控制器(对齐 Python controller/feature.py)
//!
//! 端点(挂载于 /geometry/features 下, 权限码 geometry:feature:{read,create,update,delete}):
//! - GET    /list          分页列表(page/size/keyword/feature_type)
//! - GET    /all           全量列表(最多 2000 条)
//! - GET    /{feature_id}  详情(不存在 404)
//! - POST   ""             创建(201, 返回新ID)
//! - PUT    /{feature_id}  更新(204)
//! - DELETE /{feature_id}  删除(204)
//! 错误契约: 裸 {"detail": 文案}, 校验错误 422 detail 为 [{loc,msg,type}]。

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::routing::{get, post};
use axum::{Json, Router};
use serde::Deserialize;

use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::extract::{AppJson, AppQuery};
use common::utils::pagination::{PaginationParams, PaginationResponse};
use module_authorization::deps::{authorize, AuthUserId};

use crate::do_::feature::{GeoFeatureCreate, GeoFeatureResponse, GeoFeatureUpdate};
use crate::services::feature as feature_service;

/// geometry:feature 资源权限校验(dom=obj=geometry, 对齐 Python require_permission("geometry", "feature", act))
async fn require_perm(user: &AuthUserId, act: &str) -> Result<(), AppError> {
    authorize(&user.0, "geometry", "feature", act).await
}

/// 名称长度校验(对齐 pydantic max_length=100, 违规 → 422)
fn validate_name(loc: &[&str], name: &str) -> Result<(), AppError> {
    if name.chars().count() > 100 {
        return Err(AppError::validation(
            loc,
            "String should have at most 100 characters",
        ));
    }
    Ok(())
}

/// 列表 query 过滤参数
#[derive(Debug, Default, Deserialize)]
struct ListQuery {
    /// 要素名称模糊搜索(max_length=100)
    #[serde(default)]
    keyword: Option<String>,
    /// 几何类型过滤(point/linestring/polygon)
    #[serde(default)]
    feature_type: Option<String>,
}

/// 子路由(路径含 /features 前缀, 由 app 主入口 nest 到 /geometry 下)
///
/// 说明: Python 侧 include_router(prefix="/features") + post("") 的最终路径为
/// "/geometry/features"(无尾斜杠), axum 的 nest 子路由无法表达无尾斜杠父路径,
/// 故在本层平铺注册完整子路径(对齐 module-file 的 nest 模式 + 父路径特例)。
pub fn router() -> Router<AppState> {
    Router::new()
        .route("/features", post(create_feature))
        .route("/features/list", get(list_features))
        .route("/features/all", get(list_all_features))
        .route(
            "/features/{feature_id}",
            get(get_feature).put(update_feature).delete(delete_feature),
        )
}

/// POST / —— 创建几何要素(201, 返回新创建要素ID)
async fn create_feature(
    State(state): State<AppState>,
    user: AuthUserId,
    AppJson(data): AppJson<GeoFeatureCreate>,
) -> Result<(StatusCode, Json<String>), AppError> {
    require_perm(&user, "create").await?;
    validate_name(&["body", "name"], &data.name)?;
    let id = feature_service::add(&state, data, &user.0).await?;
    Ok((StatusCode::CREATED, Json(id)))
}

/// GET /all —— 查询全部几何要素(不分页, 供地球场景一次性渲染)
async fn list_all_features(
    State(state): State<AppState>,
    user: AuthUserId,
) -> Result<Json<Vec<GeoFeatureResponse>>, AppError> {
    require_perm(&user, "read").await?;
    let items = feature_service::list_all(&state).await?;
    Ok(Json(items))
}

/// GET /list —— 分页查询几何要素列表(支持名称/类型多字段过滤)
async fn list_features(
    State(state): State<AppState>,
    user: AuthUserId,
    AppQuery(pagination): AppQuery<PaginationParams>,
    AppQuery(q): AppQuery<ListQuery>,
) -> Result<Json<PaginationResponse<GeoFeatureResponse>>, AppError> {
    require_perm(&user, "read").await?;
    pagination.validate()?;
    if let Some(keyword) = &q.keyword {
        validate_name(&["query", "keyword"], keyword)?;
    }
    let page = feature_service::list_paged(
        &state,
        &pagination,
        q.keyword.as_deref(),
        q.feature_type.as_deref(),
    )
    .await?;
    Ok(Json(page))
}

/// GET /{feature_id} —— 获取单个几何要素详情(不存在 404, 文案对齐 Python)
async fn get_feature(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(feature_id): Path<String>,
) -> Result<Json<GeoFeatureResponse>, AppError> {
    require_perm(&user, "read").await?;
    let feature = feature_service::get(&state, &feature_id)
        .await?
        .ok_or_else(|| AppError::not_found(format!("未找到ID为 {feature_id} 的几何要素")))?;
    Ok(Json(feature))
}

/// PUT /{feature_id} —— 更新几何要素(重命名/重绘几何体) — 204
async fn update_feature(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(feature_id): Path<String>,
    AppJson(data): AppJson<GeoFeatureUpdate>,
) -> Result<StatusCode, AppError> {
    require_perm(&user, "update").await?;
    if let Some(name) = &data.name {
        validate_name(&["body", "name"], name)?;
    }
    feature_service::update(&state, &feature_id, data).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// DELETE /{feature_id} —— 按ID删除几何要素(不存在 404) — 204
async fn delete_feature(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(feature_id): Path<String>,
) -> Result<StatusCode, AppError> {
    require_perm(&user, "delete").await?;
    feature_service::delete(&state, &feature_id).await?;
    Ok(StatusCode::NO_CONTENT)
}
