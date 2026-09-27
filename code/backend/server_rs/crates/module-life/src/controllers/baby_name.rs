//! 宝宝取名控制器(对齐 Python module_life/controller/baby_name.py)
//!
//! 路由前缀 /life/baby-names(nest 到 /life): 参考体系严格推算 + AI 起名(流式) + 名字管理。
//! 控制器只做请求解析/权限校验/响应包装, 业务规则与数据读写分别在 services/dao 层。
//! 注意: LLM 流式链路(module-ai)尚未迁移到 Rust, /generate 与 /predict-baby-info-base
//! 保留路由并复刻 Python 的模型可用性前置校验(默认公共 chat 模型回退链),
//! 校验通过后统一返回 400 "起名模型不可用, 请检查模型配置是否停用"。

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::routing::{get, post};
use axum::{Json, Router};

use module_authorization::do_::entity::user;
use module_authorization::deps::{AuthUser, authorize};

use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::extract::{AppJson, AppQuery};
use common::utils::pagination::{
    InfiniteScrollParams, InfiniteScrollResponse, PaginationParams, PaginationResponse,
};

use crate::do_::almanac::ReferenceCalculateResult;
use crate::do_::baby_name::{BabyNameBatchDelete, BabyNameCreate, BabyNameOut, BabyNameUpdate};
use crate::do_::predict::{
    BabyNameGenerateRequest, NameInfoBase, NameInfoPredictFullRequest, NameInfoPreference,
    NameInfoResultBase, NameInfoResultExplanation, NameInfoResultList, ReferenceCalculateRequest,
};
use crate::services;
use crate::utils::baby_name::folklore;

/// life:baby_name 资源权限校验
async fn require_perm(user: &user::Model, act: &str) -> Result<(), AppError> {
    authorize(&user.id, "life", "baby_name", act).await
}

// ==================== 参考体系目录与推算 ====================

/// GET /references —— 获取起名参考体系目录(供前端多选卡片渲染)
pub async fn get_references(
    AuthUser(actor): AuthUser,
) -> Result<Json<Vec<folklore::ReferenceCatalogItem>>, AppError> {
    require_perm(&actor, "read").await?;
    Ok(Json(services::baby_name::get_reference_catalog()))
}

/// POST /calculate-reference —— 按选中参考体系做经典严格程序推算
pub async fn calculate_reference(
    AuthUser(actor): AuthUser,
    AppJson(req): AppJson<ReferenceCalculateRequest>,
) -> Result<Json<ReferenceCalculateResult>, AppError> {
    require_perm(&actor, "read").await?;
    Ok(Json(services::baby_name::calculate_reference(req)?))
}

// ==================== AI 起名(流式) ====================

/// POST /generate —— 按参考配置流式起名(SSE)
///
/// LLM 流式链路(module-ai)尚未迁移: 复刻模型可用性前置校验后按模型不可用返回 400。
pub async fn generate_baby_names(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppJson(req): AppJson<BabyNameGenerateRequest>,
) -> Result<StatusCode, AppError> {
    require_perm(&actor, "generate").await?;
    services::baby_name::ensure_model_available(&state.db, req.model_id.as_deref().unwrap_or(""))
        .await?;
    Err(AppError::business(
        "起名模型不可用, 请检查模型配置是否停用",
    ))
}

// ==================== 兼容旧端点 ====================

/// POST /predict-name-info-preference —— 严格推算五行喜用与星座(经典算法, 非LLM估算)
pub async fn predict_name_info_preference(
    AuthUser(actor): AuthUser,
    AppJson(req): AppJson<NameInfoBase>,
) -> Result<Json<NameInfoPreference>, AppError> {
    require_perm(&actor, "read").await?;
    Ok(Json(services::baby_name::predict_preference(req)?))
}

/// POST /predict —— 推测宝宝名字(桩实现: 非流式端点, 完整起名请走 /generate)
pub async fn predict_baby_name(
    AuthUser(actor): AuthUser,
    AppJson(_req): AppJson<NameInfoBase>,
) -> Result<Json<NameInfoResultList>, AppError> {
    require_perm(&actor, "read").await?;
    Ok(Json(NameInfoResultList { results: vec![] }))
}

/// POST /predict-baby-info-base —— 按请求中的 model_id 加载 LLM 流式推测(SSE)
///
/// LLM 流式链路尚未迁移: 保留路由并统一按模型不可用返回 400(Python 缺配置时为 500)。
pub async fn predict_baby_info_base(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppJson(req): AppJson<NameInfoPredictFullRequest>,
) -> Result<StatusCode, AppError> {
    require_perm(&actor, "generate").await?;
    services::baby_name::ensure_model_available(&state.db, &req.model_id).await?;
    Err(AppError::business(
        "起名模型不可用, 请检查模型配置是否停用",
    ))
}

/// POST /predict-name-info-preference-meaning —— 反推偏好与寓意(桩实现)
pub async fn predict_name_info_preference_meaning(
    AuthUser(actor): AuthUser,
    AppJson(_req): AppJson<NameInfoResultBase>,
) -> Result<Json<NameInfoResultExplanation>, AppError> {
    require_perm(&actor, "read").await?;
    // 保留桩实现: 结构化解释暂未开放(空字符串结构)
    Ok(Json(NameInfoResultExplanation {
        explanation_wuxing: String::new(),
        explanation_constellation: String::new(),
        explanation_meaning: String::new(),
    }))
}

// ==================== 名字管理 ====================

/// POST "" —— 添加宝宝名字(201; 返回名字ID)
pub async fn create_baby_name(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppJson(data): AppJson<BabyNameCreate>,
) -> Result<(StatusCode, Json<String>), AppError> {
    require_perm(&actor, "create").await?;
    let id = services::baby_name::create(&state.db, data).await?;
    Ok((StatusCode::CREATED, Json(id)))
}

/// GET "" —— 分页查询宝宝名字列表(无排序, 与 Python list_paged 一致)
pub async fn list_baby_names(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppQuery(pagination): AppQuery<PaginationParams>,
) -> Result<Json<PaginationResponse<BabyNameOut>>, AppError> {
    require_perm(&actor, "read").await?;
    pagination.validate()?;
    Ok(Json(services::baby_name::list(&state.db, &pagination).await?))
}

/// GET /scroll —— 无限滚动加载宝宝名字列表(last_id 游标 + 排序字段)
pub async fn infinite_scroll(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppQuery(params): AppQuery<InfiniteScrollParams>,
) -> Result<Json<InfiniteScrollResponse<BabyNameOut>>, AppError> {
    require_perm(&actor, "read").await?;
    Ok(Json(services::baby_name::scroll(&state.db, &params).await?))
}

/// GET /{name_id} —— 获取单个宝宝名字详情(不存在 404 "名字不存在")
pub async fn get_baby_name(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(name_id): Path<String>,
) -> Result<Json<BabyNameOut>, AppError> {
    require_perm(&actor, "read").await?;
    Ok(Json(services::baby_name::get(&state.db, &name_id).await?))
}

/// PUT /{name_id} —— 更新宝宝名字(204; 仅显式传入的字段生效; 不存在 404)
pub async fn update_baby_name(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(name_id): Path<String>,
    AppJson(data): AppJson<BabyNameUpdate>,
) -> Result<StatusCode, AppError> {
    require_perm(&actor, "update").await?;
    services::baby_name::update(&state.db, &name_id, data).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// DELETE /{name_id} —— 删除宝宝名字(204; 不存在 404)
pub async fn delete_baby_name(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(name_id): Path<String>,
) -> Result<StatusCode, AppError> {
    require_perm(&actor, "delete").await?;
    services::baby_name::delete(&state.db, &name_id).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// POST /batch-delete —— 批量删除宝宝名字(返回实际删除条数)
pub async fn batch_delete_baby_names(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppJson(data): AppJson<BabyNameBatchDelete>,
) -> Result<Json<i64>, AppError> {
    require_perm(&actor, "delete").await?;
    Ok(Json(
        services::baby_name::batch_delete(&state.db, data.ids).await?,
    ))
}

/// 宝宝取名子路由(nest 到 /life/baby-names 前缀)
pub fn router() -> Router<AppState> {
    Router::new()
        .route(
            "/",
            get(list_baby_names).post(create_baby_name),
        )
        .route("/references", get(get_references))
        .route("/calculate-reference", post(calculate_reference))
        .route("/generate", post(generate_baby_names))
        .route("/predict-name-info-preference", post(predict_name_info_preference))
        .route("/predict", post(predict_baby_name))
        .route("/predict-baby-info-base", post(predict_baby_info_base))
        .route(
            "/predict-name-info-preference-meaning",
            post(predict_name_info_preference_meaning),
        )
        .route("/scroll", get(infinite_scroll))
        .route("/batch-delete", post(batch_delete_baby_names))
        .route(
            "/{name_id}",
            get(get_baby_name).put(update_baby_name).delete(delete_baby_name),
        )
}
