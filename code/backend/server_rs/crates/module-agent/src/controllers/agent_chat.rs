//! 智能体聊天控制器(对齐 Python controller/agent_chat.py; SSE 流式对话)
//!
//! agent 由对话记录的 agent_id 决定(前端无需传); 建流前的校验错误走 HTTP 错误契约,
//! 流内异常转为 RUN_ERROR 事件帧推送(错误即运行终态)。

use std::convert::Infallible;

use axum::extract::{Path, State};
use axum::response::sse::{Event, KeepAlive, Sse};
use axum::response::{IntoResponse, Response};
use axum::routing::post;
use axum::Router;
use tokio_stream::StreamExt;

use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::extract::AppJson;
use module_authorization::deps::{authorize, AuthUser};

use crate::do_::agent_chat::AgentChatRequest;
use crate::services::agent_chat as svc;

/// POST "/{conversation_id}/chat" —— 智能体流式聊天(SSE, AG-UI 协议)
///
/// 帧序列: RUN_STARTED → STEP_STARTED(chat)+rag.status 进度 →
/// [REASONING_* 思考流 / TEXT_MESSAGE_* 正文流 ×N] → RUN_FINISHED(或 RUN_ERROR);
/// 每帧为独立 AG-UI 事件 JSON(`data: {json}`)
pub async fn chat_stream(
    State(state): State<AppState>,
    Path(conversation_id): Path<String>,
    AuthUser(current_user): AuthUser,
    AppJson(req): AppJson<AgentChatRequest>,
) -> Result<Response, AppError> {
    authorize(&current_user.id, "agent", "chat", "write").await?;
    // stream_chat 已返回编码完成的 AG-UI 帧流(ReceiverStream<String>)
    let stream = svc::stream_chat(&state, &conversation_id, &current_user.id, &req.message)
        .map(|frame| Ok::<_, Infallible>(Event::default().data(frame)));
    Ok(Sse::new(stream)
        .keep_alive(KeepAlive::default())
        .into_response())
}

/// 智能体聊天子路由(nest 到 /agent-chat 前缀)
pub fn router() -> Router<AppState> {
    Router::new().route("/{conversation_id}/chat", post(chat_stream))
}
