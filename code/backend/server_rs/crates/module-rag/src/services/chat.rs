//! 对话/消息/知识库问答业务服务(对齐 Python module_rag/service/conversation.py、
//! chat_message.py、conversation_title.py、rag_chat.py)
//!
//! 降级约定: 向量检索/意图分析图未在 Rust 服务实现, 问答采用
//! "会话历史 + 用户问题直连对话模型"的退化链路, rag.status 事件向
//! 前端注明该口径。
//!
//! SSE 事件协议为官方 AG-UI(见 module_ai::utils::agui): RUN_STARTED(+
//! STATE_SNAPSHOT 初始状态) → rag.status 进度/REASONING 思考流/
//! TEXT_MESSAGE_* 正文流 → RUN_FINISHED/RUN_ERROR; threadId 即 conversation_id。

use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::pagination::{PaginationParams, PaginationResponse};
use sea_orm::Set;
use tokio_stream::wrappers::ReceiverStream;

use module_ai::utils::agui::{AguiStreamItem, AguiStreamTransformer};

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

// ==================== 知识库问答(SSE, AG-UI 协议) ====================

/// 发送一组已编码 AG-UI 帧到 SSE 通道; 发送失败(客户端断开)返回 false
async fn send_frames(tx: &tokio::sync::mpsc::Sender<Result<String, AppError>>, frames: Vec<String>) -> bool {
    for frame in frames {
        if tx.send(Ok(frame)).await.is_err() {
            return false;
        }
    }
    true
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

/// 知识库问答主流程(SSE 流, AG-UI 协议): 存用户消息 → 模型解析提示 → 会话历史直连 LLM →
/// 流式回答 → 落库 assistant 消息 → 自动标题
///
/// 返回事件流(每项为 SSE data 的官方 AG-UI 事件 JSON, 见 module_ai::utils::agui)
pub async fn chat_stream(
    state: AppState,
    conversation_id: String,
    user_id: String,
    req: ChatRequest,
) -> Result<ReceiverStream<Result<String, AppError>>, AppError> {
    // 0. AG-UI 转换器(threadId 即 conversation_id, 附初始状态快照供前端恢复上下文)
    let mut transformer = AguiStreamTransformer::new(&conversation_id).with_initial_state(
        serde_json::json!({
            "conversationId": conversation_id,
            "projectIds": req.project_ids,
            "deepThinking": req.deep_thinking,
        }),
    );

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
            // 无可用模型: RUN_STARTED + RUN_ERROR 终止 + 落库空 assistant 消息(带过程区块, 对齐 Python finally 口径)
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
            let mut frames = transformer.start_frames();
            frames.extend(transformer.fail(msg));
            let _ = send_frames(&tx, frames).await;
            return Ok(ReceiverStream::new(rx));
        }
    };

    // start 帧: RUN_STARTED(+STATE_SNAPSHOT)
    let _ = send_frames(&tx, transformer.start_frames()).await;

    // 3. 知识检索(会话关联项目混合检索 top 5; 未启用/无结果/失败均降级直答)
    let project_ids: Vec<String> = dao::conversation_get(&state.db, &conversation_id)
        .await
        .ok()
        .flatten()
        .map(|c| {
            c.project_ids
                .as_array()
                .map(|arr| {
                    arr.iter()
                        .filter_map(|v| v.as_str().map(String::from))
                        .collect()
                })
                .unwrap_or_default()
        })
        .unwrap_or_default();
    let mut system_prompt = crate::do_::prompts::RAG_CHAT_SYSTEM_PROMPT.to_string();
    let mut status_text = String::from("向量库未启用， 将基于会话历史直接回答");
    if !project_ids.is_empty() {
        match crate::services::document::search_by_question(
            &state,
            &user_id,
            crate::do_::document::SearchByQuestionRequest {
                project_ids,
                query_content: String::new(),
                query_text: req.message.clone(),
                limit: 5,
                score_threshold: 0.0,
                enable_rerank: false,
                rerank_limit: 0,
            },
        )
        .await
        {
            Ok(hits) => {
                let arr = hits.as_array().cloned().unwrap_or_default();
                if arr.is_empty() {
                    status_text = String::from("知识库中未检索到相关内容， 将基于会话历史直接回答");
                } else {
                    status_text = format!("已检索到 {} 条知识片段， 正在结合知识库回答", arr.len());
                    // 知识片段编号拼接进 system prompt(对齐 Python knowledge prompt 口径)
                    let ctx: Vec<String> = arr
                        .iter()
                        .enumerate()
                        .map(|(i, hit)| {
                            format!(
                                "[{}] {}",
                                i + 1,
                                hit.get("content").and_then(|c| c.as_str()).unwrap_or("")
                            )
                        })
                        .collect();
                    system_prompt.push_str(&format!(
                        "\n\n以下是检索到的知识库内容片段， 请优先依据这些内容回答用户问题， 引用知识时标注片段编号:\n{}",
                        ctx.join("\n\n")
                    ));
                }
            }
            Err(e) => {
                status_text = format!("知识检索失败({e})， 将基于会话历史直接回答");
            }
        }
    }
    if resolved.fallback_used && !resolved.binding_unset {
        status_text.push_str("; 绑定的对话模型不可用，已回退系统公共模型（数据将由公共模型处理，可在设置中调整）");
    }
    process_blocks.push(ProcessBlock {
        event_type: crate::do_::chat::stream_event_type::STATUS.to_string(),
        node_name: String::new(),
        content: status_text.clone(),
    });
    // 检索/回退提示: CUSTOM(rag.status)
    let _ = send_frames(
        &tx,
        transformer.handle_item(&AguiStreamItem::Status {
            node: String::new(),
            message: status_text.clone(),
        }),
    )
    .await;

    // 4. 会话历史(最近 20 条, 含刚存入的用户消息)直连 LLM
    let history = dao::message_list_recent(&state.db, &conversation_id, 20).await?;
    let mut messages: Vec<module_ai::do_::llm::Message> =
        vec![module_ai::do_::llm::Message {
            role: "system".to_string(),
            content: system_prompt,
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
            // RUN_ERROR 即运行终态, 不再发 RUN_FINISHED
            let _ = send_frames(&tx, transformer.fail(&msg)).await;
            return Ok(ReceiverStream::new(rx));
        }
    };

    let db = state.db.clone();
    let conv_id = conversation_id.clone();
    let title_state = state.clone();
    let node_name = crate::do_::chat::graph_node::CHAT.to_string();
    tokio::spawn(async move {
        let mut transformer = transformer;
        let mut full_response = String::new();
        let mut thinking_text = String::new();
        let mut errored = false;

        // chat 节点开始: 步骤切换(STEP_STARTED) + 进度提示(对齐 NODE_STATUS_MAP["chat"])
        if !send_frames(
            &tx,
            transformer.handle_item(&AguiStreamItem::Status {
                node: node_name.clone(),
                message: node_status(&node_name).to_string(),
            }),
        )
        .await
        {
            return; // 客户端断开
        }

        // 拉流转发: 思考增量 → REASONING 流, 正文增量 → TEXT_MESSAGE 流
        let mut rx_stream = stream;
        while let Some(item) = rx_stream.recv().await {
            match item {
                Ok(module_ai::utils::llm::StreamDelta::Content(text)) => {
                    full_response.push_str(&text);
                    let frames =
                        transformer.handle_item(&AguiStreamItem::Answer { delta: text });
                    if !send_frames(&tx, frames).await {
                        return; // 客户端断开
                    }
                }
                Ok(module_ai::utils::llm::StreamDelta::Reasoning(text)) => {
                    thinking_text.push_str(&text);
                    let frames = transformer.handle_item(&AguiStreamItem::Reasoning {
                        node: node_name.clone(),
                        delta: text,
                    });
                    if !send_frames(&tx, frames).await {
                        return; // 客户端断开
                    }
                }
                Err(e) => {
                    errored = true;
                    // RUN_ERROR 即运行终态
                    let _ = send_frames(
                        &tx,
                        transformer.handle_item(&AguiStreamItem::Error { message: e.to_string() }),
                    )
                    .await;
                    break;
                }
            }
        }
        // 收尾帧(正常: 闭消息/推理段/步骤 + RUN_FINISHED; 已错误: 不再发)
        let _ = send_frames(&tx, transformer.finalize()).await;
        // 思考过程落 blocks(前端折叠区恢复)
        if !thinking_text.is_empty() {
            process_blocks.push(ProcessBlock {
                event_type: crate::do_::chat::stream_event_type::LLM_THINKING.to_string(),
                node_name: node_name.clone(),
                content: thinking_text,
            });
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

/// 构造 RUN_ERROR 事件帧(controller 层流式异常降级用, 对齐 Python agui_event_generator 兜底)
pub fn error_frame(msg: &str) -> String {
    module_ai::utils::agui::encode_agui_event(module_ai::utils::agui::RunErrorEvent {
        base: module_ai::utils::agui::BaseEvent::default(),
        message: msg.to_string(),
        code: None,
    })
}
