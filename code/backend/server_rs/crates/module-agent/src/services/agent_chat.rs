//! 智能体流式聊天服务(对齐 Python module_agent/service/agent_chat.py)
//!
//! 基于 langgraph 单节点 StateGraph(通用 chat 节点, system_prompt 由对话关联的
//! agent 记录动态注入, 一个图结构服务所有内置/自定义智能体), 会话上下文由
//! checkpointer 按 thread_id=conversation_id 隔离持久化:
//! - postgres 部署: PostgresSaver(复用 sea-orm 连接池, 官方迁移建 checkpoints 表)
//! - sqlite 部署: SqliteSaver(同理)
//! - 其他后端/初始化失败: 降级无 checkpointer, 历史改用 chat_message 表最近若干条
//!
//! SSE 输出统一为官方 AG-UI 协议(见 module_ai::utils::agui):
//! RUN_STARTED → rag.status 进度 / REASONING_* 思考流 / TEXT_MESSAGE_* 正文流 →
//! RUN_FINISHED/RUN_ERROR; 消息持久化双轨: 图状态(messages 通道)走 checkpointer,
//! 消息记录(供前端会话列表/折叠区恢复)走 chat_message 表。

use std::collections::HashMap;
use std::sync::{Arc, Mutex as StdMutex};

use sea_orm::DatabaseConnection;
use serde_json::{json, Value};
use tokio::sync::{mpsc, Mutex};
use tokio_stream::wrappers::ReceiverStream;
use tokio_stream::StreamExt;

use common::runtime::AppState;
use common::utils::error::AppError;

use langgraph::channels::{Channel, LastValue};
use langgraph::checkpoint::BaseCheckpointSaver;
use langgraph::prelude::{
    CompiledStateGraph, GraphError, RunnableConfig, RunnableError, StateGraph, StreamMode, END,
    START,
};
use langgraph_checkpoint_postgres_rs::PostgresSaver;
use langgraph_checkpoint_sqlite_rs::SqliteSaver;

use module_ai::do_::llm::Message;
use module_ai::services::llm as llm_service;
use module_ai::utils::agui::{AguiStreamItem, AguiStreamTransformer};
use module_ai::utils::llm::{self, LlmTarget};
use module_rag::do_::entity::sea_orm_active_enums::Roletype;

use crate::dao::agent as agent_dao;
use crate::dao::rag as rag_dao;
use crate::seed::DEFAULT_AGENT_SYSTEM_PROMPT;

/// 通用聊天节点名(与前端过程区块协议/AG-UI 步骤名对齐)
pub const CHAT_NODE: &str = "chat";

/// chat 节点开始的状态提示文案(对齐 NODE_STATUS_MAP)
const CHAT_STATUS_TEXT: &str = "正在生成回答…";

/// 历史上下文条数上限(无 checkpointer 降级时: 按时间正序取最近 N 条消息)
const HISTORY_LIMIT: u64 = 20;

/// 标题最大长度(与会话列表展示截断一致)
const TITLE_MAX_LEN: usize = 20;

/// 自动标题系统提示词(照抄 module_rag SUMMARIZE_SYSTEM_PROMPT)
const SUMMARIZE_SYSTEM_PROMPT: &str = "你是一个对话总结助手。请分析给定的对话历史,生成以下两项内容,以json格式返回:\n\
1. title: 一个简短的对话标题(不超过10字,概括对话主题,以用户问题为主)\n\
2. summary: 一段对话总结(不超过50字,概括对话关键信息)";

/// 图状态通道名(LastValue 覆盖语义; messages 由节点全量重写, 等价 add_messages 累积效果)
const CH_MESSAGES: &str = "messages";
const CH_SYSTEM_PROMPT: &str = "system_prompt";
const CH_USER_ID: &str = "user_id";
const CH_USER_MESSAGE: &str = "user_message";

/// checkpointer 全局单例(postgres/sqlite 部署各初始化一次; 失败降级 None)
static CHECKPOINTER: tokio::sync::OnceCell<Option<Arc<dyn BaseCheckpointSaver>>> =
    tokio::sync::OnceCell::const_new();

/// 节点执行结果回传(供主任务落库/自动标题; 客户端中止时已生成部分仍保留)
#[derive(Default)]
struct RunOutcome {
    full_response: String,
    thinking: String,
}

/// 获取(并按需初始化)checkpointer: 复用 sea-orm 连接池 + 官方迁移建表
async fn get_checkpointer(db: &DatabaseConnection) -> Option<Arc<dyn BaseCheckpointSaver>> {
    CHECKPOINTER
        .get_or_init(|| async {
            let saver: Arc<dyn BaseCheckpointSaver> = match db {
                DatabaseConnection::SqlxPostgresPoolConnection(_) => {
                    let saver =
                        PostgresSaver::new(db.get_postgres_connection_pool().clone());
                    if let Err(e) = saver.setup().await {
                        tracing::error!("Postgres checkpointer 初始化失败(降级无 checkpointer): {e}");
                        return None;
                    }
                    Arc::new(saver)
                }
                DatabaseConnection::SqlxSqlitePoolConnection(_) => {
                    let saver =
                        SqliteSaver::new(db.get_sqlite_connection_pool().clone());
                    if let Err(e) = saver.setup().await {
                        tracing::error!("Sqlite checkpointer 初始化失败(降级无 checkpointer): {e}");
                        return None;
                    }
                    Arc::new(saver)
                }
                _ => return None,
            };
            Some(saver)
        })
        .await
        .clone()
}

/// 智能体流式聊天入口: 建流后立即返回已编码 AG-UI 帧接收器, 整个图执行在后台任务
///
/// 帧序列(AG-UI): RUN_STARTED → STEP_STARTED(chat)+rag.status →
/// [REASONING_* / TEXT_MESSAGE_* ×N] → RUN_FINISHED(或 RUN_ERROR 即运行终态)。
/// 消息持久化与自动标题在流结束后完成(客户端中止也保留已生成的部分回答)。
pub fn stream_chat(
    state: &AppState,
    conversation_id: &str,
    user_id: &str,
    message: &str,
) -> ReceiverStream<String> {
    let (tx, rx) = mpsc::channel::<String>(64);
    let db = state.db.clone();
    let http = state.http.clone();
    let conversation_id = conversation_id.to_string();
    let user_id = user_id.to_string();
    let message = message.to_string();
    tokio::spawn(async move {
        let transformer = Arc::new(Mutex::new(AguiStreamTransformer::new(&conversation_id)));
        let outcome = Arc::new(StdMutex::new(RunOutcome::default()));

        // RUN_STARTED
        for frame in transformer.lock().await.start_frames() {
            if tx.send(frame).await.is_err() {
                return; // 客户端断开
            }
        }

        // 建流准备: 解析提示词 + 回退历史(无 checkpointer 时) + 落库用户消息
        let system_prompt = match resolve_system_prompt(&db, &conversation_id).await {
            Ok(p) => p,
            Err(e) => {
                tracing::error!("智能体流式聊天准备阶段失败 conversation_id={conversation_id}: {e}");
                emit_run_error(&transformer, &tx, e.to_string()).await;
                return;
            }
        };
        let checkpointer = get_checkpointer(&db).await;
        let fallback_history = if checkpointer.is_none() {
            // 降级路径: 先取历史(不含当前消息)再落库当前消息, 当前消息作为图输入
            match rag_dao::chat_message_list(&db, &conversation_id, HISTORY_LIMIT).await {
                Ok(rows) => rows
                    .into_iter()
                    .map(|m| json!({"role": role_str(&m.role), "content": m.content}))
                    .collect(),
                Err(e) => {
                    tracing::warn!("读取会话历史失败(按空历史继续) conversation_id={conversation_id}: {e}");
                    Vec::new()
                }
            }
        } else {
            Vec::new() // 有 checkpointer: 历史随图状态恢复, input 不写 messages 以免覆盖
        };
        if let Err(e) =
            rag_dao::chat_message_add(&db, &conversation_id, Roletype::User, &message, None).await
        {
            tracing::error!("用户消息落库失败 conversation_id={conversation_id}: {e}");
            emit_run_error(&transformer, &tx, e.to_string()).await;
            return;
        }

        // 组图并执行(线程隔离: config.configurable.thread_id = conversation_id)
        let graph = build_chat_graph(db.clone(), transformer.clone(), tx.clone(), outcome.clone());
        let compiled = match graph {
            Ok(g) => match attach_checkpointer(g, checkpointer) {
                Ok(c) => c,
                Err(e) => {
                    emit_run_error(&transformer, &tx, format!("图编译失败: {e}")).await;
                    return;
                }
            },
            Err(e) => {
                emit_run_error(&transformer, &tx, format!("图构建失败: {e}")).await;
                return;
            }
        };
        let mut input = json!({
            CH_SYSTEM_PROMPT: system_prompt,
            CH_USER_ID: user_id,
            CH_USER_MESSAGE: message,
        });
        if !fallback_history.is_empty() {
            input[CH_MESSAGES] = Value::Array(fallback_history);
        }
        let config: RunnableConfig = HashMap::from([(
            "configurable".to_string(),
            json!({"thread_id": conversation_id}),
        )]);
        let mut stream = compiled.astream(&input, &config, vec![StreamMode::Updates]);
        // astream 的节点/图错误以 Debug 帧 {"error": ...} 下发(见 run_pregel_streaming)
        let mut graph_error: Option<String> = None;
        while let Some(part) = stream.next().await {
            if part.mode == StreamMode::Debug {
                if let Some(err) = part.data.get("error").and_then(Value::as_str) {
                    graph_error = Some(err.to_string());
                    break;
                }
            }
        }
        if let Some(err) = graph_error {
            tracing::error!("智能体流式聊天失败 conversation_id={conversation_id}: {err}");
            emit_run_error(&transformer, &tx, format!("服务异常: {err}")).await;
            return;
        }

        // 正常收尾: 闭消息/推理段/步骤 + RUN_FINISHED
        for frame in transformer.lock().await.finalize() {
            let _ = tx.send(frame).await;
        }

        // 持久化助手消息(部分回答也落库, 便于重新打开时恢复) + 首轮自动标题
        let o = outcome.lock().expect("结果缓冲锁").clone_owned();
        if !o.full_response.is_empty() {
            let blocks = (!o.thinking.is_empty()).then(|| {
                json!([{
                    "event_type": "llm_thinking",
                    "node_name": CHAT_NODE,
                    "content": o.thinking,
                }])
            });
            if let Err(e) = rag_dao::chat_message_add(
                &db,
                &conversation_id,
                Roletype::Assistant,
                &o.full_response,
                blocks,
            )
            .await
            {
                tracing::error!("助手消息持久化失败 conversation_id={conversation_id}: {e}");
            }
            let http2 = http.clone();
            let conv_id = conversation_id.clone();
            let user_id2 = {
                // user_id 已被 move 进 input, 从中取回
                input
                    .get(CH_USER_ID)
                    .and_then(Value::as_str)
                    .unwrap_or_default()
                    .to_string()
            };
            let user_message = message.clone();
            let full_response = o.full_response.clone();
            tokio::spawn(async move {
                maybe_auto_title(
                    &db,
                    &http2,
                    &conv_id,
                    &user_id2,
                    &user_message,
                    &full_response,
                )
                .await;
            });
        }
    });
    rx.into()
}

/// 发送 RUN_ERROR 并按协议收尾(错误即运行终态, 不再发 RUN_FINISHED)
async fn emit_run_error(
    transformer: &Arc<Mutex<AguiStreamTransformer>>,
    tx: &mpsc::Sender<String>,
    message: String,
) {
    let mut t = transformer.lock().await;
    let frames = t.handle_item(&AguiStreamItem::Error { message });
    for frame in frames {
        let _ = tx.send(frame).await;
    }
    // 已错误时 finalize 不再产出任何帧, 此处调用仅为状态一致
    let frames = t.finalize();
    for frame in frames {
        let _ = tx.send(frame).await;
    }
}

impl RunOutcome {
    /// 克隆出结果字段(供落库)
    fn clone_owned(&self) -> RunOutcome {
        RunOutcome {
            full_response: self.full_response.clone(),
            thinking: self.thinking.clone(),
        }
    }
}

/// 角色枚举 → LLM role 字符串
fn role_str(role: &Roletype) -> &'static str {
    match role {
        Roletype::User => "user",
        Roletype::Assistant => "assistant",
        Roletype::System => "system",
    }
}

/// 构建单节点聊天图: START → chat → END
///
/// chat 节点(对齐 Python _chat_node): 解析用户模型 → system_prompt+历史+当前输入
/// 直连 LLM 流式生成, token 经共享 AguiStreamTransformer 翻译为 AG-UI 帧即时下发;
/// 节点返回全量 messages(含本轮 user/assistant 消息, LastValue 覆盖等价累积)。
fn build_chat_graph(
    db: DatabaseConnection,
    transformer: Arc<Mutex<AguiStreamTransformer>>,
    tx: mpsc::Sender<String>,
    outcome: Arc<StdMutex<RunOutcome>>,
) -> Result<StateGraph, GraphError> {
    let mut channels: HashMap<String, Box<dyn Channel>> = HashMap::new();
    for key in [CH_MESSAGES, CH_SYSTEM_PROMPT, CH_USER_ID, CH_USER_MESSAGE] {
        channels.insert(key.to_string(), Box::new(LastValue::new(key)));
    }
    let mut graph = StateGraph::new(channels);
    graph.add_node(CHAT_NODE, move |input: Value, _config: RunnableConfig| {
        let db = db.clone();
        let transformer = transformer.clone();
        let tx = tx.clone();
        let outcome = outcome.clone();
        async move {
            // 1. 读取图状态(checkpointer 恢复的 messages 历史 + 本轮输入)
            let system_prompt = input
                .get(CH_SYSTEM_PROMPT)
                .and_then(Value::as_str)
                .unwrap_or_default();
            let user_id = input
                .get(CH_USER_ID)
                .and_then(Value::as_str)
                .unwrap_or_default();
            let user_message = input
                .get(CH_USER_MESSAGE)
                .and_then(Value::as_str)
                .unwrap_or_default();
            let history: Vec<Value> = input
                .get(CH_MESSAGES)
                .and_then(Value::as_array)
                .cloned()
                .unwrap_or_default();

            // 2. 解析用户可用对话模型(绑定校验 → 回退开关 → 默认公共模型)
            let Some(target) = resolve_chat_model(&db, user_id).await else {
                return Err(RunnableError::Node(
                    "无可用对话模型, 请先在模型配置中绑定或由管理员配置公共模型".to_string(),
                ));
            };

            // 3. chat 节点开始: STEP_STARTED + rag.status 进度提示
            let frames = transformer.lock().await.handle_item(&AguiStreamItem::Status {
                node: CHAT_NODE.to_string(),
                message: CHAT_STATUS_TEXT.to_string(),
            });
            for frame in frames {
                let _ = tx.send(frame).await;
            }

            // 4. 组装消息(system_prompt + 历史 + 当前输入)并流式生成
            let mut messages: Vec<Message> = Vec::with_capacity(history.len() + 2);
            messages.push(llm_message("system", system_prompt));
            for m in &history {
                let role = m.get("role").and_then(Value::as_str).unwrap_or("user");
                let content = m.get("content").and_then(Value::as_str).unwrap_or_default();
                messages.push(llm_message(role, content));
            }
            messages.push(llm_message("user", user_message));

            let mut chunks = llm::chat_stream(target, &messages)
                .map_err(|e| RunnableError::Node(e.to_string()))?;
            let mut full_response = String::new();
            let mut thinking = String::new();
            let mut client_gone = false;
            while let Some(item) = chunks.recv().await {
                let frames = match item {
                    // 正文增量 → TEXT_MESSAGE_CONTENT
                    Ok(llm::StreamDelta::Content(text)) => {
                        full_response.push_str(&text);
                        transformer
                            .lock()
                            .await
                            .handle_item(&AguiStreamItem::Answer { delta: text })
                    }
                    // 思考增量 → REASONING_MESSAGE_CONTENT(按 chat 节点分段)
                    Ok(llm::StreamDelta::Reasoning(text)) => {
                        thinking.push_str(&text);
                        transformer.lock().await.handle_item(&AguiStreamItem::Reasoning {
                            node: CHAT_NODE.to_string(),
                            delta: text,
                        })
                    }
                    // 中途异常上抛, 由 astream 的 Debug 帧转 RUN_ERROR
                    Err(e) => return Err(RunnableError::Node(e.to_string())),
                };
                if !client_gone {
                    for frame in frames {
                        if tx.send(frame).await.is_err() {
                            // 客户端已断开: 停止发帧, 继续拉流保住已生成部分用于落库
                            client_gone = true;
                            break;
                        }
                    }
                }
            }

            // 5. 回传全量 messages(含本轮对话) + 结果缓冲
            {
                let mut o = outcome.lock().expect("结果缓冲锁");
                o.full_response = full_response.clone();
                o.thinking = thinking;
            }
            let mut new_messages = history;
            new_messages.push(json!({"role": "user", "content": user_message}));
            new_messages.push(json!({"role": "assistant", "content": full_response}));
            Ok(json!({ CH_MESSAGES: new_messages }))
        }
    })?;
    graph.add_edge(START, CHAT_NODE)?;
    graph.add_edge(CHAT_NODE, END)?;
    // 编译(含 checkpointer 挂载)由 attach_checkpointer 统一执行
    Ok(graph)
}

/// 挂载 checkpointer 编译(None 时编译为无持久化图)
fn attach_checkpointer(
    graph: StateGraph,
    checkpointer: Option<Arc<dyn BaseCheckpointSaver>>,
) -> Result<CompiledStateGraph, GraphError> {
    let mut graph = graph;
    let mut builder = graph.compile_builder();
    if let Some(cp) = checkpointer {
        builder = builder.checkpointer(cp);
    }
    builder.build()
}

/// 单条 LLM 消息构造
fn llm_message(role: &str, content: &str) -> Message {
    Message {
        role: role.to_string(),
        content: content.to_string(),
        additional_kwargs: Value::Null,
    }
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

use module_ai::dao::model_config as model_config_dao;

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
    fn 角色枚举转llm字符串() {
        assert_eq!(role_str(&Roletype::User), "user");
        assert_eq!(role_str(&Roletype::Assistant), "assistant");
        assert_eq!(role_str(&Roletype::System), "system");
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

    /// 单节点图端到端: 状态经 messages 通道(LastValue 覆盖)累积两轮对话
    #[tokio::test]
    async fn 单节点图累积对话状态() {
        use langgraph::prelude::*;

        let mut channels: HashMap<String, Box<dyn Channel>> = HashMap::new();
        for key in [CH_MESSAGES, CH_SYSTEM_PROMPT, CH_USER_ID, CH_USER_MESSAGE] {
            channels.insert(key.to_string(), Box::new(LastValue::new(key)));
        }
        let mut graph = StateGraph::new(channels);
        graph
            .add_node(CHAT_NODE, |input: Value, _config: RunnableConfig| async move {
                // 模拟 LLM 回显: 历史 + 当前消息全量返回(节点返回值写回 messages)
                let mut history: Vec<Value> = input
                    .get(CH_MESSAGES)
                    .and_then(Value::as_array)
                    .cloned()
                    .unwrap_or_default();
                let user_message = input
                    .get(CH_USER_MESSAGE)
                    .and_then(Value::as_str)
                    .unwrap_or_default();
                history.push(json!({"role": "user", "content": user_message}));
                history.push(json!({"role": "assistant", "content": format!("回声: {user_message}")}));
                Ok(json!({ CH_MESSAGES: history }))
            })
            .expect("add_node");
        graph.add_edge(START, CHAT_NODE).expect("add_edge start");
        graph.add_edge(CHAT_NODE, END).expect("add_edge end");
        let compiled = graph.compile().expect("compile");

        // 两轮对话共用 thread_id, 验证 messages 跨调用累积(checkpoint 语义由
        // 生产链路的 checkpointer 提供, 此处用 update_state 模拟第二轮输入)
        let config: RunnableConfig = HashMap::from([(
            "configurable".to_string(),
            json!({"thread_id": "t1"}),
        )]);
        let r1 = compiled
            .ainvoke(
                &json!({ CH_USER_MESSAGE: "你好", CH_USER_ID: "u", CH_SYSTEM_PROMPT: "p" }),
                &config,
            )
            .await
            .expect("第一轮");
        let msgs1 = r1.get(CH_MESSAGES).and_then(Value::as_array).expect("messages");
        assert_eq!(msgs1.len(), 2);
        assert_eq!(msgs1[1]["content"], "回声: 你好");

        // 第二轮: 以第一轮输出为状态输入(等价 checkpointer 恢复)
        let mut input2 = json!({ CH_USER_MESSAGE: "再见", CH_USER_ID: "u", CH_SYSTEM_PROMPT: "p" });
        input2[CH_MESSAGES] = r1.get(CH_MESSAGES).cloned().unwrap();
        let r2 = compiled.ainvoke(&input2, &config).await.expect("第二轮");
        let msgs2 = r2.get(CH_MESSAGES).and_then(Value::as_array).expect("messages");
        assert_eq!(msgs2.len(), 4, "历史应跨轮累积");
        assert_eq!(msgs2[3]["content"], "回声: 再见");
    }
}
