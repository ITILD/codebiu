//! LLM 控制器(对齐 Python controller/llm.py; 前缀 /llm)
//!
//! - POST /chat: 流式返回 SSE 事件流(start → stream×N → end/error, 载荷与
//!   Python sse_starlette 一致为 `data: {json}`), 非流式返回模型 content JSON
//! - 配置校验/能力测试/缓存清理端点与 Python 错误语义对齐(ValueError→404, 其余→500)

use std::convert::Infallible;

use axum::extract::{Path, Query, State};
use axum::response::sse::{Event, KeepAlive, Sse};
use axum::response::{IntoResponse, Response};
use axum::routing::{delete, post};
use axum::{Json, Router};
use serde::Deserialize;
use tokio::sync::mpsc;
use tokio_stream::wrappers::ReceiverStream;

use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::extract::AppJson;

use crate::do_::llm::{
    ChatRequest, ModelConfigCheckResponse, ModelTestRequest, ModelTestResponse,
};
use crate::do_::model_config::ModelConfigCreateRequest;
use crate::services::llm as svc;
use crate::utils::llm::StreamChunkResponse;

/// POST /check-config —— 配置校验(连通性 + 格式化能力)
pub async fn check_config(
    State(state): State<AppState>,
    AppJson(req): AppJson<ModelConfigCreateRequest>,
) -> Result<Json<ModelConfigCheckResponse>, AppError> {
    req.validate()?;
    Ok(Json(svc::check_config(&state.http, &req).await))
}

/// POST /check-config-by-model-id 查询参数
#[derive(Debug, Deserialize)]
pub struct ModelIdQuery {
    pub model_id: String,
}

/// POST /check-config-by-model-id —— 按模型配置ID校验有效性
pub async fn check_config_by_model_id(
    State(state): State<AppState>,
    Query(query): Query<ModelIdQuery>,
) -> Result<Json<serde_json::Value>, AppError> {
    let valid = svc::check_config_by_model_id(&state.db, &state.http, &query.model_id).await?;
    let message = if valid {
        "配置校验通过"
    } else {
        "配置校验失败:智能程度低"
    };
    Ok(Json(serde_json::json!({ "message": message })))
}

/// POST /test-by-model-id —— 模型能力测试(结果持久化到 check_result)
///
/// :raises: AppError::not_found 模型配置不存在(404, 对齐 Python ValueError)
pub async fn test_by_model_id(
    State(state): State<AppState>,
    AppJson(req): AppJson<ModelTestRequest>,
) -> Result<Json<ModelTestResponse>, AppError> {
    let result = svc::test_and_persist(
        &state.db,
        &state.http,
        &req.model_id,
        req.capability.as_deref(),
    )
    .await?;
    Ok(Json(result))
}

/// POST /chat —— 聊天接口(支持流式 SSE)
///
/// 流式: 事件载荷与 Python StreamChunkResponse 同构(start/chunk 共用 response_id)
/// 非流式: 直接返回模型 content(字符串或分段数组)
pub async fn chat_completion(
    State(state): State<AppState>,
    AppJson(req): AppJson<ChatRequest>,
) -> Result<Response, AppError> {
    let messages = req.messages.to_messages()?;
    // 配置不存在/方案未实现 → 404(对齐 Python ValueError); 实例经缓存装载
    let target = svc::get_llm(&state.db, &req.model_id, req.streaming)
        .await?
        .ok_or_else(|| AppError::not_found(format!("模型配置不存在: {}", req.model_id)))?;
    if req.streaming {
        // 组装 SSE 事件流: start → stream×N → end/error
        let mut chunks = crate::utils::llm::chat_stream(target, &messages)?;
        let start = StreamChunkResponse::start();
        let response_id = start.response_id.clone();
        let (tx, rx) = mpsc::channel::<Result<Event, Infallible>>(64);
        tokio::spawn(async move {
            let send = |event: Result<Event, Infallible>| {
                let tx = tx.clone();
                async move { tx.send(event).await }
            };
            let _ = send(Ok(Event::default().data(start.to_json()))).await;
            let mut errored = false;
            while let Some(item) = chunks.recv().await {
                match item {
                    Ok(text) => {
                        let chunk = StreamChunkResponse::chunk(&response_id, text);
                        if send(Ok(Event::default().data(chunk.to_json())))
                            .await
                            .is_err()
                        {
                            // 客户端已断开, 终止拉流
                            return;
                        }
                    }
                    Err(e) => {
                        // 中途异常转为 SSE error 事件(载荷携带错误文案)
                        let err = StreamChunkResponse::error(e.to_string());
                        let _ = send(Ok(Event::default().data(err.to_json()))).await;
                        errored = true;
                        break;
                    }
                }
            }
            if !errored {
                let end = StreamChunkResponse::end();
                let _ = send(Ok(Event::default().data(end.to_json()))).await;
            }
        });
        Ok(Sse::new(ReceiverStream::new(rx))
            .keep_alive(KeepAlive::default())
            .into_response())
    } else {
        // 非流式: 调用失败统一 500 "模型调用失败: {e}"(对齐 Python 异常处理器)
        let content = crate::utils::llm::chat_once(&state.http, &target, &messages)
            .await
            .map_err(|e| AppError::internal(format!("模型调用失败: {e}")))?;
        Ok(Json(content).into_response())
    }
}

/// DELETE /cache/{model_id} —— 按 model_id 前缀清除模型实例缓存
pub async fn clear_cache(Path(model_id): Path<String>) -> Json<serde_json::Value> {
    svc::clear_cache(Some(&model_id));
    Json(serde_json::json!({ "message": format!("模型 {model_id} 缓存已清除") }))
}

/// LLM 子路由(nest 到 /llm 前缀)
pub fn router() -> Router<AppState> {
    Router::new()
        .route("/chat", post(chat_completion))
        .route("/check-config", post(check_config))
        .route("/check-config-by-model-id", post(check_config_by_model_id))
        .route("/test-by-model-id", post(test_by_model_id))
        .route("/cache/{model_id}", delete(clear_cache))
}
