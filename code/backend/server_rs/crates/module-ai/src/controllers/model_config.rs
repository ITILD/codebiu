//! 模型配置控制器(对齐 Python controller/model_config.py; 前缀 /model-configs)
//!
//! 权限: 全局管理员可见/可操作全部; 其他用户按可见性(公共/部门/本人)访问,
//! 写操作仅创建者本人或管理员。url/api_key 对非本人私有模型脱敏。

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::routing::{get, post};
use axum::{Json, Router};
use serde::Deserialize;

use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::extract::{AppJson, AppQuery};
use common::utils::pagination::{
    InfiniteScrollParams, InfiniteScrollResponse, PaginationParams, PaginationResponse,
};
use module_authorization::deps::AuthUser;

use crate::dao::model_config as dao;
use crate::do_::entity::model_config;
use crate::do_::model_config::{
    ModelConfigCreateRequest, ModelConfigResp, ModelConfigUpdate, ModelScope,
};
use crate::services::model_config as svc;

/// 判断用户是否为全局管理员(可见全部模型配置, 对齐 Python _is_admin)
async fn is_admin(user_id: &str) -> bool {
    module_authorization::casbin_mgr::auth()
        .has_grouping_policy(user_id, "admin", "*")
        .await
}

/// POST "" —— 创建模型配置(201; 响应体为 JSON 字符串 id)
pub async fn create_model_config(
    State(state): State<AppState>,
    AuthUser(current_user): AuthUser,
    AppJson(req): AppJson<ModelConfigCreateRequest>,
) -> Result<(StatusCode, Json<String>), AppError> {
    req.validate()?;
    let mut create = req.into_create(current_user.id.clone());
    // 部门模型: 归属当前用户所在部门(必须已有部门)
    if create.scope == ModelScope::Dept {
        let dept_id = current_user.dept_id.clone().filter(|s| !s.is_empty());
        let Some(dept_id) = dept_id else {
            return Err(AppError::business("创建部门模型需要先加入部门"));
        };
        create.dept_id = Some(dept_id);
    }
    let id = svc::add(&state.db, &state.http, create).await?;
    Ok((StatusCode::CREATED, Json(id)))
}

/// GET /list 查询参数(多字段过滤)
#[derive(Debug, Deserialize)]
pub struct ModelConfigListQuery {
    /// 模型标识名称模糊搜索
    #[serde(default)]
    pub model: Option<String>,
    /// 模型类型过滤(chat/embeddings/rerank 等)
    #[serde(default)]
    pub model_type: Option<String>,
    /// 服务类型过滤(openai/dashscope/vllm/ollama/aws)
    #[serde(default)]
    pub server_type: Option<String>,
    /// 归属范围过滤(public/dept/user)
    #[serde(default)]
    pub scope: Option<String>,
    /// 按所有者用户名模糊过滤(仅管理员生效)
    #[serde(default)]
    pub user: Option<String>,
}

/// GET /list —— 分页获取模型配置列表(多字段过滤 + 可见性 + 脱敏)
pub async fn list_model_configs(
    State(state): State<AppState>,
    AppQuery(pagination): AppQuery<PaginationParams>,
    AppQuery(query): AppQuery<ModelConfigListQuery>,
    AuthUser(current_user): AuthUser,
) -> Result<Json<PaginationResponse<model_config::Model>>, AppError> {
    pagination.validate()?;
    let admin = is_admin(&current_user.id).await;
    // 仅管理员支持按所有者用户名过滤(先解析为用户ID列表)
    let mut filter_user_ids: Option<Vec<String>> = None;
    if let Some(user) = query.user.as_deref().filter(|s| !s.is_empty()) {
        if admin {
            let ids = dao::search_user_ids_by_username(&state.db, user).await?;
            if ids.is_empty() {
                return Ok(Json(PaginationResponse::create(vec![], 0, &pagination)));
            }
            filter_user_ids = Some(ids);
        }
    }
    let mut result = svc::list_paged(
        &state.db,
        &pagination,
        query.model.as_deref(),
        query.model_type.as_deref(),
        query.server_type.as_deref(),
        query.scope.as_deref(),
        Some(&current_user.id),
        current_user.dept_id.as_deref(),
        admin,
        filter_user_ids.as_deref(),
    )
    .await?;
    // 脱敏: 管理员豁免(可见明文账号/密码); 其他用户仅本人私有模型保留明文
    svc::mask_secrets(&mut result.items, &current_user.id, admin);
    Ok(Json(result))
}

/// GET /scroll —— 无限滚动获取模型配置列表(按当前用户可见性过滤 + 脱敏)
pub async fn infinite_scroll_model_configs(
    State(state): State<AppState>,
    AppQuery(params): AppQuery<InfiniteScrollParams>,
    AuthUser(current_user): AuthUser,
) -> Result<Json<InfiniteScrollResponse<model_config::Model>>, AppError> {
    let admin = is_admin(&current_user.id).await;
    let mut result = svc::get_scroll(
        &state.db,
        &params,
        Some(&current_user.id),
        current_user.dept_id.as_deref(),
        admin,
    )
    .await?;
    svc::mask_secrets(&mut result.items, &current_user.id, admin);
    Ok(Json(result))
}

/// GET /{id} —— 获取单个模型配置(不存在 404; 非本人私有模型脱敏)
pub async fn get_model_config(
    State(state): State<AppState>,
    Path(id): Path<String>,
    AuthUser(current_user): AuthUser,
) -> Result<Json<ModelConfigResp>, AppError> {
    let mut config = svc::get(&state.db, &id)
        .await?
        .ok_or_else(|| AppError::not_found(format!("未找到ID为 {id} 的模型配置")))?;
    svc::mask_secret(&mut config, &current_user.id, is_admin(&current_user.id).await);
    Ok(Json(ModelConfigResp::from(config)))
}

/// PUT /{id} —— 更新模型配置(204; 仅创建者本人或全局管理员)
pub async fn update_model_config(
    State(state): State<AppState>,
    Path(id): Path<String>,
    AuthUser(current_user): AuthUser,
    AppJson(patch): AppJson<ModelConfigUpdate>,
) -> Result<StatusCode, AppError> {
    let existing = svc::get(&state.db, &id)
        .await?
        .ok_or_else(|| AppError::not_found(format!("未找到ID为 {id} 的模型配置")))?;
    if !(is_admin(&current_user.id).await || existing.user_id == current_user.id) {
        return Err(AppError::forbidden(
            "无权修改该模型配置(仅创建者本人或全局管理员)",
        ));
    }
    svc::update(&state.db, &state.http, &id, patch).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// DELETE /{id} —— 删除模型配置(204; 仅创建者本人或全局管理员)
pub async fn delete_model_config(
    State(state): State<AppState>,
    Path(id): Path<String>,
    AuthUser(current_user): AuthUser,
) -> Result<StatusCode, AppError> {
    let existing = svc::get(&state.db, &id)
        .await?
        .ok_or_else(|| AppError::not_found(format!("未找到ID为 {id} 的模型配置")))?;
    if !(is_admin(&current_user.id).await || existing.user_id == current_user.id) {
        return Err(AppError::forbidden(
            "无权删除该模型配置(仅创建者本人或全局管理员)",
        ));
    }
    svc::delete(&state.db, &id).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// GET /default-params/{model_name} —— 获取默认模型参数kv
pub async fn get_default_model_params(
    Path(model_name): Path<String>,
) -> Result<Json<serde_json::Value>, AppError> {
    let params = svc::get_default_params(&model_name).await?;
    Ok(Json(serde_json::json!({ "params": params })))
}

/// 模型配置子路由(nest 到 /model-configs 前缀)
pub fn router() -> Router<AppState> {
    Router::new()
        .route("/", post(create_model_config))
        .route("/list", get(list_model_configs))
        .route("/scroll", get(infinite_scroll_model_configs))
        .route("/default-params/{model_name}", get(get_default_model_params))
        .route(
            "/{id}",
            get(get_model_config).put(update_model_config).delete(delete_model_config),
        )
}
