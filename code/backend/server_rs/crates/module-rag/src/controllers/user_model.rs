//! 用户-模型绑定控制器(对齐 Python module_rag/controller/user_model.py; 挂载前缀 /rag)

use axum::extract::State;
use axum::routing::get;
use axum::{Json, Router};
use common::runtime::AppState;
use common::utils::error::AppError;

use module_authorization::deps::AuthUserId;

use crate::do_::user_model::{UserModelResponse, UserModelUpdate};
use crate::services::user_model as svc;

/// 获取当前用户的模型绑定(未绑定返回空绑定)
async fn get_my_model_binding(
    State(state): State<AppState>,
    user: AuthUserId,
) -> Result<Json<UserModelResponse>, AppError> {
    Ok(Json(svc::get_by_user(&state, &user.0).await?))
}

/// 更新当前用户的模型绑定(归一化/校验/落库在服务层)
async fn update_my_model_binding(
    State(state): State<AppState>,
    user: AuthUserId,
    Json(req): Json<UserModelUpdate>,
) -> Result<Json<UserModelResponse>, AppError> {
    Ok(Json(svc::upsert(&state, &user.0, req).await?))
}

pub(crate) fn user_models_router() -> Router<AppState> {
    Router::new().route("/my", get(get_my_model_binding).put(update_my_model_binding))
}
