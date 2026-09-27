//! 对话/知识库问答控制器(对齐 Python module_rag/controller/conversation.py、
//! rag_chat.py; 挂载前缀 /rag)

use axum::extract::{Path, Query, State};
use axum::http::StatusCode;
use axum::response::sse::{Event, KeepAlive, KeepAliveStream, Sse};
use axum::routing::{get, post};
use axum::{Json, Router};
use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::pagination::{PaginationParams, PaginationResponse};
use futures::StreamExt;
use serde::Deserialize;
use tokio_stream::wrappers::ReceiverStream;

use module_authorization::deps::{authorize, AuthUserId};

use crate::do_::chat::{
    ChatMessageResponse, ChatRequest, ConversationCreate, ConversationResponse, ConversationSummary,
    ConversationUpdate,
};
use crate::services::chat as svc;

/// casbin 权限校验(rag 域)
async fn require_perm(user: &AuthUserId, obj: &str, act: &str) -> Result<(), AppError> {
    authorize(&user.0, "rag", obj, act).await
}

/// 内存分页(DAO 返回全量后切片)
fn paginate<T>(items: Vec<T>, pagination: &PaginationParams) -> PaginationResponse<T> {
    let total = items.len() as i64;
    let page = items
        .into_iter()
        .skip(pagination.offset() as usize)
        .take(pagination.limit() as usize)
        .collect();
    PaginationResponse::create(page, total, pagination)
}

// ==================== query 参数载体 ====================

#[derive(Debug, Deserialize)]
struct MyListQuery {
    #[serde(flatten)]
    pagination: PaginationParams,
    #[serde(default = "d_scope")]
    scope: String,
}

fn d_scope() -> String {
    "all".to_string()
}

/// 聊天消息分页参数(允许更大的 size 1~1000, 对齐 Python ChatMessagePaginationParams)
#[derive(Debug, Deserialize)]
struct MessageListQuery {
    #[serde(flatten)]
    pagination: PaginationParams,
}

impl MessageListQuery {
    /// 自定义校验(size 上限放宽至 1000)
    fn validate(&self) -> Result<(), AppError> {
        if self.pagination.page < 1 {
            return Err(AppError::validation(&["query", "page"], "Input should be greater than or equal to 1"));
        }
        if self.pagination.size < 1 {
            return Err(AppError::validation(&["query", "size"], "size 必须大于等于 1"));
        }
        if self.pagination.size > 1000 {
            return Err(AppError::validation(&["query", "size"], "size 不能超过 1000"));
        }
        Ok(())
    }
}

// ==================== 对话管理(/rag/conversations) ====================

/// 创建对话(201 返回对话ID)
async fn create_conversation(
    State(state): State<AppState>,
    user: AuthUserId,
    Json(data): Json<ConversationCreate>,
) -> Result<(StatusCode, Json<String>), AppError> {
    let id = svc::conversation_create(&state, &user.0, data).await?;
    Ok((StatusCode::CREATED, Json(id)))
}

/// 分页获取当前用户的对话列表(scope: all/rag/agent)
async fn list_my_conversations(
    State(state): State<AppState>,
    user: AuthUserId,
    Query(q): Query<MyListQuery>,
) -> Result<Json<PaginationResponse<ConversationResponse>>, AppError> {
    Ok(Json(
        svc::conversation_list_my(&state, &user.0, &q.scope, &q.pagination).await?,
    ))
}

/// 获取对话详情(404 "对话未找到")
async fn get_conversation(
    State(state): State<AppState>,
    _user: AuthUserId,
    Path(conversation_id): Path<String>,
) -> Result<Json<ConversationResponse>, AppError> {
    Ok(Json(svc::conversation_get(&state, &conversation_id).await?))
}

/// 更新对话(204; 仅本人可改, 对话不存在或非本人统一 404)
async fn update_conversation(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(conversation_id): Path<String>,
    Json(data): Json<ConversationUpdate>,
) -> Result<StatusCode, AppError> {
    svc::conversation_update(&state, &conversation_id, &user.0, data).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// 删除对话并级联删消息(204)
async fn delete_conversation(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(conversation_id): Path<String>,
) -> Result<StatusCode, AppError> {
    svc::conversation_delete(&state, &conversation_id, &user.0).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// 获取对话消息列表(size 1~1000)
async fn list_messages(
    State(state): State<AppState>,
    _user: AuthUserId,
    Path(conversation_id): Path<String>,
    Query(q): Query<MessageListQuery>,
) -> Result<Json<PaginationResponse<ChatMessageResponse>>, AppError> {
    q.validate()?;
    let items = svc::message_list(&state, &conversation_id).await?;
    Ok(Json(paginate(items, &q.pagination)))
}

pub(crate) fn conversations_router() -> Router<AppState> {
    Router::new()
        .route("/", post(create_conversation))
        .route("/my", get(list_my_conversations))
        .route(
            "/{conversation_id}",
            get(get_conversation).put(update_conversation).delete(delete_conversation),
        )
        .route("/{conversation_id}/messages", get(list_messages))
}

// ==================== 知识库问答(/rag/rag-chat) ====================

/// SSE 响应体类型(keep-alive 包装后的 mpsc 接收流)
type SseResponse = Sse<KeepAliveStream<ReceiverStream<Result<Event, std::convert::Infallible>>>>;

/// 流式聊天(SSE): 每帧为一条 data 事件, 内容为 StreamChunkResponse JSON
///
/// 流式体内的异常转为 ERROR 事件推送(对齐 Python event_generator 行为)
async fn chat_stream(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(conversation_id): Path<String>,
    Json(chat_request): Json<ChatRequest>,
) -> Result<SseResponse, AppError> {
    require_perm(&user, "chat", "write").await?;
    // 建流前的校验错误(404/400 等)由全局异常处理器映射状态码
    let stream = svc::chat_stream(state, conversation_id, user.0, chat_request).await?;
    let (tx, rx) = tokio::sync::mpsc::channel::<
        Result<axum::response::sse::Event, std::convert::Infallible>,
    >(64);
    tokio::spawn(async move {
        let mut stream = stream;
        while let Some(item) = stream.next().await {
            let event = match item {
                Ok(frame) => Ok(axum::response::sse::Event::default().data(frame)),
                // 流式体内异常 → ERROR 事件(对齐 Python event_generator)
                Err(e) => Ok(axum::response::sse::Event::default()
                    .data(svc::error_frame(&e.to_string()))),
            };
            if tx.send(event).await.is_err() {
                break; // 客户端断开
            }
        }
    });
    Ok(Sse::new(ReceiverStream::new(rx)).keep_alive(KeepAlive::default()))
}

/// 总结历史对话并生成标题(失败降级返回默认空摘要)
async fn summarize_conversation(
    State(state): State<AppState>,
    user: AuthUserId,
    Path(conversation_id): Path<String>,
) -> Result<Json<ConversationSummary>, AppError> {
    require_perm(&user, "chat", "write").await?;
    Ok(Json(svc::summarize(&state, &conversation_id, &user.0).await?))
}

pub(crate) fn rag_chat_router() -> Router<AppState> {
    Router::new()
        .route("/{conversation_id}/chat", post(chat_stream))
        .route("/{conversation_id}/summarize", post(summarize_conversation))
}
