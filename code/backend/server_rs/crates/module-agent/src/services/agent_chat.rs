//! 智能体流式聊天服务(对齐 Python module_agent/service/agent_chat.py)
//!
//! Python 基于 LangGraph 单节点图 + Postgres checkpointer 保存会话历史; Rust 侧简化为
//! 直连 LLM 流式调用(module-ai pub API), 会话上下文改用 chat_message 表最近若干条历史。
//!
//! SSE 事件协议(对齐 module_ai event_generator + module_rag StreamOne):
//! - start 帧: 分配 response_id, 后续业务帧复用
//! - 业务事件(STATUS/ANSWER/ERROR): 均为 status=stream 的普通帧, 携带 node_name 与
//!   stream_event_type; ERROR 事件 node_name 为空串(而非 error status 帧)
//! - end 帧: status=end, 新 response_id
//! - 准备阶段异常(resolve 提示词/落库用户消息): status=error 帧终止, 不发 end 帧

use sea_orm::DatabaseConnection;
use serde_json::Value;
use tokio::sync::mpsc;

use common::runtime::AppState;
use common::utils::error::AppError;

use module_ai::dao::model_config as model_config_dao;
use module_ai::do_::llm::Message;
use module_ai::services::llm as llm_service;
use module_ai::utils::llm::{self, LlmTarget, StreamChunkResponse, StreamStatus};
use module_rag::do_::entity::chat_message;
use module_rag::do_::entity::sea_orm_active_enums::Roletype;

use crate::dao::agent as agent_dao;
use crate::dao::rag as rag_dao;
use crate::seed::DEFAULT_AGENT_SYSTEM_PROMPT;

/// 通用聊天节点名(与前端过程区块协议对齐)
pub const CHAT_NODE: &str = "chat";

/// 流式事件分类: 状态提示
const EVT_STATUS: &str = "status";
/// 流式事件分类: 正式回答
const EVT_ANSWER: &str = "answer";
/// 流式事件分类: 异常
const EVT_ERROR: &str = "error";

/// chat 节点开始的状态提示文案(对齐 NODE_STATUS_MAP)
const CHAT_STATUS_TEXT: &str = "正在生成回答…";

/// 历史上下文条数上限(checkpointer 替代方案: 按时间正序取最近 N 条消息)
const HISTORY_LIMIT: u64 = 20;

/// 标题最大长度(与会话列表展示截断一致)
const TITLE_MAX_LEN: usize = 20;

/// 自动标题系统提示词(照抄 module_rag SUMMARIZE_SYSTEM_PROMPT)
const SUMMARIZE_SYSTEM_PROMPT: &str = "你是一个对话总结助手。请分析给定的对话历史,生成以下两项内容,以json格式返回:\n\
1. title: 一个简短的对话标题(不超过10字,概括对话主题,以用户问题为主)\n\
2. summary: 一段对话总结(不超过50字,概括对话关键信息)";

/// 业务事件帧构造(status=stream, 复用 start 的 response_id; 对齐 event_generator 的映射)
fn event_frame(
    response_id: &str,
    content: &str,
    node_name: &str,
    event_type: &str,
) -> StreamChunkResponse {
    StreamChunkResponse {
        status: StreamStatus::Stream,
        role: "assistant",
        content: Some(content.to_string()),
        response_id: response_id.to_string(),
        timestamp: 0.0,
        node_name: Some(node_name.to_string()),
        stream_event_type: Some(event_type.to_string()),
    }
}

/// 单条 LLM 消息构造
fn llm_message(role: &str, content: &str) -> Message {
    Message {
        role: role.to_string(),
        content: content.to_string(),
        additional_kwargs: Value::Null,
    }
}

/// 智能体流式聊天入口: 建流后立即返回接收器, 整个流程在后台任务执行
///
/// 帧序列: start → [status/answer×N] → end; 异常按阶段分别转为 error 帧或 error 事件帧。
/// 对话/消息持久化与自动标题在流结束后完成(客户端中止也保留已生成的部分回答)。
pub fn stream_chat(
    state: &AppState,
    conversation_id: &str,
    user_id: &str,
    message: &str,
) -> mpsc::Receiver<StreamChunkResponse> {
    let (tx, rx) = mpsc::channel(64);
    let db = state.db.clone();
    let http = state.http.clone();
    let conversation_id = conversation_id.to_string();
    let user_id = user_id.to_string();
    let message = message.to_string();
    tokio::spawn(async move {
        // start 帧(分配 response_id)
        let start = StreamChunkResponse::start();
        let response_id = start.response_id.clone();
        let _ = tx.send(start).await;

        // 建流准备: 解析提示词 + 读取历史 + 落库用户消息; 失败 → error status 帧终止(无 end 帧)
        let prepared = prepare(&db, &conversation_id, &message).await;
        let (system_prompt, history) = match prepared {
            Ok(pair) => pair,
            Err(e) => {
                tracing::error!("智能体流式聊天准备阶段失败 conversation_id={conversation_id}: {e}");
                let _ = tx.send(StreamChunkResponse::error(e.to_string())).await;
                return;
            }
        };

        // 主流程: 失败 → ERROR 事件(error chunk 帧, node_name 空串), 之后仍正常发 end 帧
        if let Err(e) = run_stream(
            &db,
            &http,
            &tx,
            &response_id,
            &conversation_id,
            &user_id,
            &system_prompt,
            &history,
            &message,
        )
        .await
        {
            tracing::error!("智能体流式聊天失败 conversation_id={conversation_id}: {e}");
            let frame = event_frame(&response_id, &format!("服务异常: {e}"), "", EVT_ERROR);
            let _ = tx.send(frame).await;
        }
        let _ = tx.send(StreamChunkResponse::end()).await;
    });
    rx
}

/// 建流准备: 解析对话关联智能体的 system_prompt + 读取历史 + 落库当前用户消息
async fn prepare(
    db: &DatabaseConnection,
    conversation_id: &str,
    message: &str,
) -> Result<(String, Vec<chat_message::Model>), AppError> {
    let system_prompt = resolve_system_prompt(db, conversation_id).await?;
    // 先取历史(不含当前消息), 再落库当前用户消息(当前消息作为本次图输入)
    let history = rag_dao::chat_message_list(db, conversation_id, HISTORY_LIMIT).await?;
    rag_dao::chat_message_add(db, conversation_id, Roletype::User, message, None).await?;
    Ok((system_prompt, history))
}

/// 流式生成主流程(对齐 _chat_node + 事件分类 + finally 落库)
async fn run_stream(
    db: &DatabaseConnection,
    http: &reqwest::Client,
    tx: &mpsc::Sender<StreamChunkResponse>,
    response_id: &str,
    conversation_id: &str,
    user_id: &str,
    system_prompt: &str,
    history: &[chat_message::Model],
    message: &str,
) -> Result<(), AppError> {
    // 解析用户可用对话模型(绑定校验 → 回退开关 → 默认公共模型); None → 报错中断
    let Some(target) = resolve_chat_model(db, user_id).await else {
        return Err(AppError::business(
            "无可用对话模型, 请先在模型配置中绑定或由管理员配置公共模型",
        ));
    };

    // 组装消息: system_prompt + 历史 + 当前输入(对齐 [SystemMessage] + messages)
    let mut messages: Vec<Message> = Vec::with_capacity(history.len() + 2);
    messages.push(llm_message("system", system_prompt));
    for m in history {
        let role = match m.role {
            Roletype::User => "user",
            Roletype::Assistant => "assistant",
            Roletype::System => "system",
        };
        messages.push(llm_message(role, &m.content));
    }
    messages.push(llm_message("user", message));

    // 节点开始: 状态提示(对齐 NODE_STATUS_MAP["chat"] 的 STATUS 事件)
    let _ = tx
        .send(event_frame(response_id, CHAT_STATUS_TEXT, CHAT_NODE, EVT_STATUS))
        .await;

    // 拉流转发: 每个 token → answer 事件帧
    let mut chunks = llm::chat_stream(target, &messages)?;
    let mut full_response = String::new();
    while let Some(item) = chunks.recv().await {
        match item {
            Ok(text) => {
                full_response.push_str(&text);
                let frame = event_frame(response_id, &text, CHAT_NODE, EVT_ANSWER);
                if tx.send(frame).await.is_err() {
                    // 客户端已断开: 停止转发, 已生成的部分回答仍走下方落库(对齐 finally 语义)
                    break;
                }
            }
            // 中途异常向上抛, 由调用方转为"服务异常" error 事件帧
            Err(e) => return Err(e),
        }
    }

    // 持久化助手消息(部分回答也落库, 便于重新打开时恢复)
    if !full_response.is_empty() {
        if let Err(e) =
            rag_dao::chat_message_add(db, conversation_id, Roletype::Assistant, &full_response, None)
                .await
        {
            tracing::error!("助手消息持久化失败 conversation_id={conversation_id}: {e}");
        }
        // 首次问答结束后自动生成会话标题(后台任务, 失败静默)
        let db2 = db.clone();
        let http2 = http.clone();
        let conv_id = conversation_id.to_string();
        let user_id = user_id.to_string();
        let user_message = message.to_string();
        tokio::spawn(async move {
            maybe_auto_title(
                &db2,
                &http2,
                &conv_id,
                &user_id,
                &user_message,
                &full_response,
            )
            .await;
        });
    }
    Ok(())
}

/// 解析对话关联智能体的 system_prompt(未关联/智能体已删除时用默认提示词兜底)
async fn resolve_system_prompt(
    db: &DatabaseConnection,
    conversation_id: &str,
) -> Result<String, AppError> {
    let prompt = match rag_dao::conversation_get(db, conversation_id).await? {
        Some(conv) => match conv.agent_id {
            Some(agent_id) => agent_dao::get(db, &agent_id)
                .await?
                .filter(|a| !a.system_prompt.is_empty())
                .map(|a| a.system_prompt),
            None => None,
        },
        None => None,
    };
    Ok(prompt.unwrap_or_else(|| DEFAULT_AGENT_SYSTEM_PROMPT.to_string()))
}

/// 解析用户可用的对话模型(非流式/流式共用解析链; 对齐 UserModelService.get_llm_by_user_id)
///
/// 解析链: 用户绑定 → 归属校验 → (回退开关允许时)默认公共模型; 任一环节失败均静默返回 None。
async fn resolve_chat_model(db: &DatabaseConnection, user_id: &str) -> Option<LlmTarget> {
    let binding = rag_dao::user_model_get(db, user_id).await.ok().flatten();
    if let Some(model_id) = binding.as_ref().and_then(|b| b.chat_model_id.clone()) {
        if validate_model_access(db, &model_id, user_id).await.is_ok() {
            return match llm_service::get_llm(db, &model_id, true).await {
                Ok(target) => target,
                Err(e) => {
                    tracing::error!("获取模型实例失败 model_id={model_id}: {e}");
                    None
                }
            };
        }
        tracing::warn!("用户 {user_id} 模型绑定校验失败, 尝试默认公共模型回退");
    }
    // 用户级回退开关: 关闭时绑定失效不回退(未配置绑定时默认允许回退)
    if binding.as_ref().is_some_and(|b| b.fallback_disabled) {
        tracing::info!("用户 {user_id} 已关闭模型回退, chat 绑定失效不回退");
        return None;
    }
    // 回退默认公共对话模型(active_only)
    match model_config_dao::get_default_by_type(db, "chat", true).await {
        Ok(Some(cfg)) => match llm_service::get_llm(db, &cfg.id, true).await {
            Ok(target) => target,
            Err(e) => {
                tracing::error!("获取默认公共模型实例失败 model_id={}: {e}", cfg.id);
                None
            }
        },
        Ok(None) => None,
        Err(e) => {
            tracing::warn!("获取默认公共模型回退失败[chat]: {e}");
            None
        }
    }
}

/// 校验模型配置使用权限(公共/本人/本部门; 停用与不存在均视为绑定失效, 对齐 _validate_model_access)
async fn validate_model_access(
    db: &DatabaseConnection,
    model_id: &str,
    user_id: &str,
) -> Result<(), AppError> {
    let no_access = || {
        AppError::business(format!(
            "无权使用模型配置: {model_id}(仅可用公共/本部门/自己的模型)"
        ))
    };
    let Some(config) = model_config_dao::get(db, model_id).await? else {
        return Err(AppError::not_found(format!("模型配置不存在: {model_id}")));
    };
    // 停用模型视为绑定失效(触发回退链)
    if !config.is_active {
        return Err(AppError::business(format!("模型配置已停用: {model_id}")));
    }
    match config.scope.as_str() {
        // 公共模型放行
        "public" => Ok(()),
        // 本人模型放行
        "user" if config.user_id == user_id => Ok(()),
        // 部门模型: 校验当前用户所属部门
        "dept" => {
            let user_dept = rag_dao::user_dept_id(db, user_id).await?;
            if user_dept.is_some() && user_dept == config.dept_id {
                Ok(())
            } else {
                Err(no_access())
            }
        }
        _ => Err(no_access()),
    }
}

/// 首次问答结束后自动生成会话标题(仅首轮消息时执行, 失败静默不影响主流程)
///
/// 结构化输出以提示词约束 JSON 并容错解析(对齐 Python with_structured_output)。
async fn maybe_auto_title(
    db: &DatabaseConnection,
    http: &reqwest::Client,
    conversation_id: &str,
    user_id: &str,
    user_message: &str,
    assistant_message: &str,
) {
    let outcome: Result<(), AppError> = async {
        let Some(conv) = rag_dao::conversation_get(db, conversation_id).await? else {
            return Ok(());
        };
        let original_title = conv.title.clone();
        // 仅首轮问答(1条用户消息+1条助手消息)后生成, 后续轮次不再改动标题
        if rag_dao::chat_message_count(db, conversation_id).await? != 2 {
            return Ok(());
        }
        // 无可用对话模型时跳过标题生成
        let Some(target) = resolve_chat_model(db, user_id).await else {
            tracing::warn!("用户 {user_id} 无可用对话模型, 跳过自动生成会话标题");
            return Ok(());
        };
        // 结构化输出: system 要求 JSON(title/summary) + 首轮问答摘要
        let prompt = format!(
            "用户提问: {}\n助手回答: {}",
            cut_chars(user_message, 2000),
            cut_chars(assistant_message, 2000)
        );
        let messages = [
            llm_message("system", SUMMARIZE_SYSTEM_PROMPT),
            llm_message("user", &prompt),
        ];
        let content = llm::chat_once(http, &target, &messages).await?;
        let parsed = crate::services::workflow::parse_json_content(
            &crate::services::workflow::content_text(&content),
        );
        let title = parsed
            .get("title")
            .and_then(Value::as_str)
            .unwrap_or("")
            .trim()
            .to_string();
        // 截断到最大长度后仍为空则不更新
        let title: String = title.chars().take(TITLE_MAX_LEN).collect();
        if title.is_empty() {
            return Ok(());
        }
        // 生成期间用户手动改名/删除会话则不覆盖
        let conv_now = rag_dao::conversation_get(db, conversation_id).await?;
        if conv_now.map(|c| c.title) != Some(original_title) {
            return Ok(());
        }
        rag_dao::conversation_update_title(db, conversation_id, &title).await?;
        Ok(())
    }
    .await;
    if let Err(e) = outcome {
        tracing::warn!("自动生成会话标题失败 conversation_id={conversation_id}: {e}");
    }
}

/// 按字符截断到指定长度(对齐 Python text[:n])
fn cut_chars(text: &str, n: usize) -> String {
    text.chars().take(n).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn 业务事件帧复用response_id且带节点信息() {
        let frame = event_frame("abc", "你好", CHAT_NODE, EVT_ANSWER);
        assert_eq!(frame.response_id, "abc");
        assert_eq!(frame.node_name.as_deref(), Some("chat"));
        assert_eq!(frame.stream_event_type.as_deref(), Some("answer"));
        let json: Value = serde_json::from_str(&frame.to_json()).expect("JSON 解析");
        // 业务帧与 Python event_generator 输出同构: status=stream(默认), node_name 载荷透传
        assert_eq!(json["status"], "stream");
        assert_eq!(json["node_name"], "chat");
        assert_eq!(json["stream_event_type"], "answer");

        // 错误事件: node_name 为空串(而非 null/error status)
        let err_frame = event_frame("abc", "服务异常: boom", "", EVT_ERROR);
        let err_json: Value = serde_json::from_str(&err_frame.to_json()).expect("JSON 解析");
        assert_eq!(err_json["status"], "stream");
        assert_eq!(err_json["node_name"], "");
        assert_eq!(err_json["stream_event_type"], "error");
    }

    #[test]
    fn start与end帧形态对齐python契约() {
        let start = StreamChunkResponse::start();
        let start_json: Value = serde_json::from_str(&start.to_json()).expect("JSON 解析");
        assert_eq!(start_json["status"], "start");
        assert_eq!(start_json["node_name"], Value::Null);

        let end_json: Value =
            serde_json::from_str(&StreamChunkResponse::end().to_json()).expect("JSON 解析");
        assert_eq!(end_json["status"], "end");
        assert_ne!(end_json["response_id"], start_json["response_id"]);
    }

    #[test]
    fn 标题提示词约束json字段() {
        let parsed = crate::services::workflow::parse_json_content(
            r#"前置 {"title": " 会话标题 ", "summary": "摘要"} 后缀"#,
        );
        let title = parsed.get("title").and_then(Value::as_str).unwrap_or("");
        assert_eq!(title.trim(), "会话标题");
        // 截断到 20 字符
        let long: String = "标".repeat(30).chars().take(TITLE_MAX_LEN).collect();
        assert_eq!(long.chars().count(), 20);
        assert_eq!(cut_chars("abcdef", 3), "abc");
    }
}
