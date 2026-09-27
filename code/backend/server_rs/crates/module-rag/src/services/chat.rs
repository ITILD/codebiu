//! 对话/消息/知识库问答业务服务(对齐 Python module_rag/service/conversation.py、
//! chat_message.py、conversation_title.py、rag_chat.py)
//!
//! 降级约定: 向量检索/意图分析图未在 Rust 服务实现, 问答采用
//! "会话历史 + 用户问题直连对话模型"的退化链路, start 事件的 status 区块向
//! 前端注明该口径; SSE 事件结构与 Python 保持同构。

use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::pagination::{PaginationParams, PaginationResponse};
use sea_orm::Set;
use tokio_stream::wrappers::ReceiverStream;

use crate::dao::chat as dao;
use crate::do_::chat::{
    node_status, string_vec_to_json, ChatMessageResponse, ChatRequest, ConversationResponse,
    ConversationSummary, ProcessBlock,
};
use crate::do_::entity::chat_message;
use crate::do_::entity::conversation;
use crate::do_::entity::sea_orm_active_enums::Roletype;
use crate::do_::prompts::SUMMARIZE_SYSTEM_PROMPT;
use crate::do_::user_model::model_type;
use crate::services::user_model as um_service;

/// 32 位 hex uuid
fn new_id() -> String {
    uuid::Uuid::new_v4().simple().to_string()
}

/// 默认对话标题(自动标题仅在标题仍为默认值时覆盖)
const DEFAULT_TITLE: &str = "新对话";

// ==================== 对话服务 ====================

/// 创建对话, 返回对话ID
pub async fn conversation_create(
    state: &AppState,
    user_id: &str,
    req: crate::do_::chat::ConversationCreate,
) -> Result<String, AppError> {
    let id = new_id();
    dao::conversation_add(
        &state.db,
        conversation::ActiveModel {
            id: Set(id.clone()),
            title: Set(req.title),
            agent_id: Set(req.agent_id),
            user_id: Set(user_id.to_string()),
            project_ids: Set(string_vec_to_json(&req.project_ids)),
            created_at: Set(Some(chrono::Utc::now().into())),
            updated_at: Set(chrono::Utc::now().into()),
        },
    )
    .await?;
    Ok(id)
}

/// 用户对话分页列表(scope: all/rag/agent)
pub async fn conversation_list_my(
    state: &AppState,
    user_id: &str,
    scope: &str,
    pagination: &PaginationParams,
) -> Result<PaginationResponse<ConversationResponse>, AppError> {
    pagination.validate()?;
    let items = dao::conversation_list_by_user(
        &state.db,
        user_id,
        scope,
        pagination.offset(),
        pagination.limit(),
    )
    .await?;
    let total = dao::conversation_count_by_user(&state.db, user_id, scope).await?;
    Ok(PaginationResponse::create(
        items.into_iter().map(ConversationResponse::from).collect(),
        total,
        pagination,
    ))
}

/// 按ID获取对话(404 "对话未找到")
pub async fn conversation_get(state: &AppState, id: &str) -> Result<ConversationResponse, AppError> {
    dao::conversation_get(&state.db, id)
        .await?
        .map(ConversationResponse::from)
        .ok_or_else(|| AppError::not_found("对话未找到"))
}

/// 更新对话(仅本人可改)
pub async fn conversation_update(
    state: &AppState,
    id: &str,
    user_id: &str,
    req: crate::do_::chat::ConversationUpdate,
) -> Result<(), AppError> {
    let m = dao::conversation_get(&state.db, id)
        .await?
        .filter(|c| c.user_id == user_id)
        .ok_or_else(|| AppError::not_found("对话未找到"))?;
    dao::conversation_update(&state.db, m, req.title, req.agent_id.map(Some), req.project_ids).await?;
    Ok(())
}

/// 删除对话(级联删消息)
pub async fn conversation_delete(state: &AppState, id: &str, user_id: &str) -> Result<(), AppError> {
    let m = dao::conversation_get(&state.db, id)
        .await?
        .filter(|c| c.user_id == user_id)
        .ok_or_else(|| AppError::not_found("对话未找到"))?;
    dao::message_delete_by_conversation(&state.db, &m.id).await?;
    dao::conversation_delete(&state.db, &m.id).await?;
    Ok(())
}

// ==================== 消息服务 ====================

/// 新增消息
pub async fn message_add(
    state: &AppState,
    conversation_id: &str,
    role: Roletype,
    content: String,
    blocks: Option<Vec<ProcessBlock>>,
) -> Result<ChatMessageResponse, AppError> {
    let blocks_json = blocks.map(|b| serde_json::to_value(b).unwrap_or(serde_json::json!([])));
    let m = dao::message_add(
        &state.db,
        chat_message::ActiveModel {
            id: Set(new_id()),
            conversation_id: Set(conversation_id.to_string()),
            role: Set(role),
            content: Set(content),
            created_at: Set(Some(chrono::Utc::now().into())),
            blocks: Set(blocks_json),
        },
    )
    .await?;
    Ok(m.into())
}

/// 对话消息列表(按时间升序)
pub async fn message_list(state: &AppState, conversation_id: &str) -> Result<Vec<ChatMessageResponse>, AppError> {
    Ok(dao::message_list_by_conversation(&state.db, conversation_id)
        .await?
        .into_iter()
        .map(ChatMessageResponse::from)
        .collect())
}

// ==================== 知识库问答(SSE, 降级链路) ====================

/// 构造 SSE 数据帧(复用 module-ai 的 StreamChunkResponse 结构, 自定义节点/事件语义)
fn sse_chunk(
    status: module_ai::utils::llm::StreamStatus,
    response_id: &str,
    content: Option<String>,
    node_name: Option<&str>,
    event_type: Option<&str>,
) -> String {
    let payload = module_ai::utils::llm::StreamChunkResponse {
        status,
        role: "assistant",
        content,
        response_id: response_id.to_string(),
        timestamp: 0.0,
        node_name: node_name.map(str::to_string),
        stream_event_type: event_type.map(str::to_string),
    };
    payload.to_json()
}

/// 自动标题(首轮问答完成后执行): 标题仍为默认值时, 由 LLM 生成不超过 20 字的标题
///
/// 失败静默(不影响问答主流程), 对齐 Python maybe_auto_title
async fn maybe_auto_title(state: &AppState, conversation_id: &str) {
    let Ok(Some(conv)) = dao::conversation_get(&state.db, conversation_id).await else {
        return;
    };
    // 标题被用户改名后不覆盖
    if conv.title != DEFAULT_TITLE {
        return;
    }
    // 仅首轮(total==2)才执行
    if dao::message_count_by_conversation(&state.db, conversation_id)
        .await
        .unwrap_or(0)
        != 2
    {
        return;
    }
    let Ok(messages) = dao::message_list_by_conversation(&state.db, conversation_id).await else {
        return;
    };
    let history: String = messages
        .iter()
        .map(|m| format!("{}: {}\n", dao::role_str(&m.role), m.content))
        .collect();
    let Some(model_id) = um_service::resolve_model(state, &conv.user_id, model_type::CHAT)
        .await
        .ok()
        .and_then(|r| r.model_id)
    else {
        return;
    };
    let Ok(Some(target)) = module_ai::services::llm::get_llm(&state.db, &model_id, false).await else {
        return;
    };
    // 对话历史作为 user 消息随 system 提示一并提供(对齐 Python 自动标题口径)
    let msgs = [
        module_ai::do_::llm::Message {
            role: "system".to_string(),
            content: SUMMARIZE_SYSTEM_PROMPT.to_string(),
            additional_kwargs: serde_json::Value::Null,
        },
        module_ai::do_::llm::Message {
            role: "user".to_string(),
            content: history,
            additional_kwargs: serde_json::Value::Null,
        },
    ];
    let Ok(content) = module_ai::utils::llm::chat_once(&state.http, &target, &msgs).await else {
        return;
    };
    // 解析 JSON 输出(title/summary): 先剥 markdown 围栏再取 title 字段
    let text = content.as_str().unwrap_or("");
    let cleaned = text
        .trim()
        .trim_start_matches("```json")
        .trim_start_matches("```")
        .trim_end_matches("```")
        .trim();
    let title = serde_json::from_str::<serde_json::Value>(cleaned)
        .ok()
        .and_then(|v| v.get("title").and_then(|t| t.as_str()).map(str::to_string))
        .map(|t| t.trim().to_string())
        .filter(|t| !t.is_empty())
        .map(|t| t.chars().take(20).collect::<String>());
    if let Some(title) = title {
        let _ = dao::conversation_update(&state.db, conv, Some(title), None, None).await;
    }
}

/// 知识库问答主流程(SSE 流): 存用户消息 → 模型解析提示 → 会话历史直连 LLM →
/// 流式回答 → 落库 assistant 消息 → 自动标题
///
/// 返回事件流(每项为 SSE data 的 JSON 字符串)
pub async fn chat_stream(
    state: AppState,
    conversation_id: String,
    user_id: String,
    req: ChatRequest,
) -> Result<ReceiverStream<Result<String, AppError>>, AppError> {
    // 1. 存用户消息
    message_add(&state, &conversation_id, Roletype::User, req.message.clone(), None).await?;

    // 2. 解析对话模型(含回退链提示)
    let resolved = um_service::resolve_model(&state, &user_id, model_type::CHAT).await?;
    let model_id = resolved.model_id;
    // 过程区块(非正式回答内容, 落库 assistant.blocks)
    let mut process_blocks: Vec<ProcessBlock> = Vec::new();

    let (tx, rx) = tokio::sync::mpsc::channel::<Result<String, AppError>>(64);
    let stream_model_id = match model_id {
        Some(id) => id,
        None => {
            // 无可用模型: ERROR 事件 + 落库空 assistant 消息(带过程区块, 对齐 Python finally 口径)
            let msg = "没有可用的对话模型(绑定失效且无默认公共模型可回退)， 请在设置中绑定模型或联系管理员配置默认模型";
            process_blocks.push(ProcessBlock {
                event_type: crate::do_::chat::stream_event_type::ERROR.to_string(),
                node_name: String::new(),
                content: msg.to_string(),
            });
            let _ = message_add(
                &state,
                &conversation_id,
                Roletype::Assistant,
                String::new(),
                Some(process_blocks.clone()),
            )
            .await;
            let _ = tx.send(Err(AppError::business(msg))).await;
            return Ok(ReceiverStream::new(rx));
        }
    };

    // start 帧
    let start = module_ai::utils::llm::StreamChunkResponse::start();
    let response_id = start.response_id.clone();
    let _ = tx.send(Ok(serde_json::to_string(&start).unwrap_or_default())).await;

    // 3. STATUS 提示: 检索退化说明 + (可选)回退提示
    let mut status_text = String::from("知识库检索引擎暂未在 Rust 服务实现, 将基于会话历史直接回答");
    if resolved.fallback_used && !resolved.binding_unset {
        status_text.push_str("; 绑定的对话模型不可用，已回退系统公共模型（数据将由公共模型处理，可在设置中调整）");
    }
    process_blocks.push(ProcessBlock {
        event_type: crate::do_::chat::stream_event_type::STATUS.to_string(),
        node_name: String::new(),
        content: status_text.clone(),
    });
    let _ = tx
        .send(Ok(sse_chunk(
            module_ai::utils::llm::StreamStatus::Stream,
            &response_id,
            Some(status_text),
            None,
            Some(crate::do_::chat::stream_event_type::STATUS),
        )))
        .await;

    // 4. 会话历史(最近 20 条, 含刚存入的用户消息)直连 LLM
    let history = dao::message_list_recent(&state.db, &conversation_id, 20).await?;
    let mut messages: Vec<module_ai::do_::llm::Message> =
        vec![module_ai::do_::llm::Message {
            role: "system".to_string(),
            content: crate::do_::prompts::RAG_CHAT_SYSTEM_PROMPT.to_string(),
            additional_kwargs: serde_json::Value::Null,
        }];
    for m in &history {
        messages.push(module_ai::do_::llm::Message {
            role: dao::role_str(&m.role).to_string(),
            content: m.content.clone(),
            additional_kwargs: serde_json::Value::Null,
        });
    }

    // 5. 建流并转发 ANSWER 事件(流式模型实例 → chat_stream 返回接收端)
    let stream = match module_ai::services::llm::get_llm(&state.db, &stream_model_id, true).await {
        Ok(Some(target)) => module_ai::utils::llm::chat_stream(target, &messages)
            .map_err(|e| e),
        Ok(None) => Err(AppError::business(format!("加载对话模型失败: {stream_model_id}"))),
        Err(e) => Err(e),
    };
    let stream = match stream {
        Ok(rx2) => rx2,
        Err(e) => {
            let msg = e.to_string();
            process_blocks.push(ProcessBlock {
                event_type: crate::do_::chat::stream_event_type::ERROR.to_string(),
                node_name: String::new(),
                content: msg.clone(),
            });
            let _ = message_add(
                &state,
                &conversation_id,
                Roletype::Assistant,
                String::new(),
                Some(process_blocks.clone()),
            )
            .await;
            let _ = tx
                .send(Ok(sse_chunk(
                    module_ai::utils::llm::StreamStatus::Error,
                    &new_id(),
                    Some(msg),
                    None,
                    Some(crate::do_::chat::stream_event_type::ERROR),
                )))
                .await;
            return Ok(ReceiverStream::new(rx));
        }
    };

    let db = state.db.clone();
    let conv_id = conversation_id.clone();
    let title_state = state.clone();
    let node_name = crate::do_::chat::graph_node::CHAT.to_string();
    tokio::spawn(async move {
        let mut full_response = String::new();
        let mut errored = false;
        let mut rx_stream = stream;
        while let Some(item) = rx_stream.recv().await {
            match item {
                Ok(text) => {
                    full_response.push_str(&text);
                    let frame = sse_chunk(
                        module_ai::utils::llm::StreamStatus::Stream,
                        &response_id,
                        Some(text),
                        Some(&node_name),
                        Some(crate::do_::chat::stream_event_type::ANSWER),
                    );
                    if tx.send(Ok(frame)).await.is_err() {
                        return; // 客户端断开
                    }
                }
                Err(e) => {
                    errored = true;
                    let msg = e.to_string();
                    let frame = sse_chunk(
                        module_ai::utils::llm::StreamStatus::Error,
                        &new_id(),
                        Some(msg.clone()),
                        None,
                        Some(crate::do_::chat::stream_event_type::ERROR),
                    );
                    let _ = tx.send(Ok(frame)).await;
                    break;
                }
            }
        }
        // end 帧(正常结束)
        if !errored {
            let end = module_ai::utils::llm::StreamChunkResponse::end();
            let _ = tx.send(Ok(serde_json::to_string(&end).unwrap_or_default())).await;
        }
        // 6. 落库 assistant 消息(content + 过程区块)
        if !full_response.is_empty() || errored {
            let blocks_json = serde_json::to_value(&process_blocks).ok();
            let _ = dao::message_add(
                &db,
                chat_message::ActiveModel {
                    id: Set(new_id()),
                    conversation_id: Set(conv_id.clone()),
                    role: Set(Roletype::Assistant),
                    content: Set(full_response),
                    created_at: Set(Some(chrono::Utc::now().into())),
                    blocks: Set(blocks_json),
                },
            )
            .await;
        }
        // 7. 首轮问答自动标题
        maybe_auto_title(&title_state, &conv_id).await;
    });
    Ok(ReceiverStream::new(rx))
}

// ==================== 对话总结 ====================

/// 对话总结: 由历史对话生成标题与摘要(标题非空才更新会话标题)
///
/// 失败/无模型返回默认值(title=""/summary=""), 对齐 Python summarize 降级行为
pub async fn summarize(
    state: &AppState,
    conversation_id: &str,
    user_id: &str,
) -> Result<ConversationSummary, AppError> {
    let conv = dao::conversation_get(&state.db, conversation_id)
        .await?
        .filter(|c| c.user_id == user_id)
        .ok_or_else(|| AppError::not_found("对话未找到"))?;
    let default = ConversationSummary::default();
    let result = try_summarize(state, &conv, user_id).await;
    match result {
        Ok(summary) => {
            // 标题非空才更新会话标题
            if !summary.title.is_empty() {
                let _ = dao::conversation_update(
                    &state.db,
                    conv,
                    Some(summary.title.clone()),
                    None,
                    None,
                )
                .await;
            }
            Ok(summary)
        }
        Err(e) => {
            tracing::warn!("对话总结生成失败(返回默认值): {e}");
            Ok(default)
        }
    }
}

/// 总结实际执行体(取历史 → chat_once → 解析 JSON)
async fn try_summarize(
    state: &AppState,
    conv: &conversation::Model,
    user_id: &str,
) -> Result<ConversationSummary, AppError> {
    let model_id = um_service::resolve_model(state, user_id, model_type::CHAT)
        .await?
        .model_id
        .ok_or_else(|| AppError::business("无可用对话模型"))?;
    let Some(target) = module_ai::services::llm::get_llm(&state.db, &model_id, false).await?
    else {
        return Err(AppError::business("加载对话模型失败"));
    };
    let messages = dao::message_list_by_conversation(&state.db, &conv.id).await?;
    let history: String = messages
        .iter()
        .map(|m| format!("{}: {}\n", dao::role_str(&m.role), m.content))
        .collect();
    let msgs = [
        module_ai::do_::llm::Message {
            role: "system".to_string(),
            content: SUMMARIZE_SYSTEM_PROMPT.to_string(),
            additional_kwargs: serde_json::Value::Null,
        },
        module_ai::do_::llm::Message {
            role: "user".to_string(),
            content: history,
            additional_kwargs: serde_json::Value::Null,
        },
    ];
    let content = module_ai::utils::llm::chat_once(&state.http, &target, &msgs).await?;
    let text = content.as_str().unwrap_or("");
    // 剥离 markdown 代码围栏(模型可能输出 ```json ... ```)
    let cleaned = text
        .trim()
        .trim_start_matches("```json")
        .trim_start_matches("```")
        .trim_end_matches("```")
        .trim();
    let parsed: serde_json::Value = serde_json::from_str(cleaned)
        .map_err(|e| AppError::internal(format!("总结 JSON 解析失败: {e}")))?;
    Ok(ConversationSummary {
        title: parsed
            .get("title")
            .and_then(|v| v.as_str())
            .unwrap_or_default()
            .trim()
            .to_string(),
        summary: parsed
            .get("summary")
            .and_then(|v| v.as_str())
            .unwrap_or_default()
            .trim()
            .to_string(),
    })
}

/// 构造 ERROR 事件帧(controller 层流式异常降级用, 对齐 Python event_generator 行为)
pub fn error_frame(msg: &str) -> String {
    sse_chunk(
        module_ai::utils::llm::StreamStatus::Error,
        &new_id(),
        Some(msg.to_string()),
        None,
        Some(crate::do_::chat::stream_event_type::ERROR),
    )
}

/// 状态提示文案(节点名 → 前端提示, 供控制器复用)
pub fn status_of(node: &str) -> String {
    node_status(node).to_string()
}
