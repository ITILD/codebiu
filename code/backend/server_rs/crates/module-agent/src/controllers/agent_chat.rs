//! 智能体聊天控制器(对齐 Python controller/agent_chat.py; SSE 流式对话)
//!
//! agent 由对话记录的 agent_id 决定(前端无需传); 建流前的校验错误走 HTTP 错误契约,
//! 流内异常转为 error 事件帧推送(与 Python event_generator 行为一致)。

use std::convert::Infallible;

use axum::extract::{Path, State};
use axum::response::sse::{Event, KeepAlive, Sse};
use axum::response::{IntoResponse, Response};
use axum::routing::post;
use axum::Router;
use tokio_stream::wrappers::ReceiverStream;
use tokio_stream::StreamExt;

use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::extract::AppJson;
use module_authorization::deps::{authorize, AuthUser};

use crate::do_::agent_chat::AgentChatRequest;
use crate::services::agent_chat as svc;

/// POST "/{conversation_id}/chat" —— 智能体流式聊天(SSE)
///
/// 帧序列: start → [status/answer×N] → end; 业务帧均复用 start 的 response_id,
/// 载荷与 Python StreamChunkResponse 同构(`data: {json}`)
pub async fn chat_stream(
    State(state): State<AppState>,
    Path(conversation_id): Path<String>,
    AuthUser(current_user): AuthUser,
    AppJson(req): AppJson<AgentChatRequest>,
) -> Result<Response, AppError> {
    authorize(&current_user.id, "agent", "chat", "write").await?;
    let frames = svc::stream_chat(&state, &conversation_id, &current_user.id, &req.message);
    let stream = ReceiverStream::new(frames)
        .map(|frame| Ok::<_, Infallible>(Event::default().data(frame.to_json())));
    Ok(Sse::new(stream)
        .keep_alive(KeepAlive::default())
        .into_response())
}

/// 智能体聊天子路由(nest 到 /agent-chat 前缀)
pub fn router() -> Router<AppState> {
    Router::new().route("/{conversation_id}/chat", post(chat_stream))
}
