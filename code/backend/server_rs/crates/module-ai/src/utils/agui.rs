//! AG-UI 协议(Agent User Interaction Protocol)事件层 — 基于官方 crate
//!
//! 官方实现: cargo 包 ``ag-ui-protocol``(lib 名 ``ag_ui_protocol``)。
//! 事件模型定义在 ``ag_ui_protocol::events``: 与官方 TS/Python SDK wire 兼容
//! (SCREAMING_SNAKE_CASE 的 ``type`` 判别 + camelCase 字段 + None 可选字段自动省略),
//! 对齐 Python 端 ``model_dump_json(by_alias=True)`` 的输出。
//! 文档: https://docs.ag-ui.com/concepts/events
//!
//! 协议分层与本项目取舍(等价 Python utils/llm/stream/agui.py):
//! - 事件模型/编码 → 官方 ``ag_ui_protocol``(本模块直接复用并 re-export, 不自实现)
//! - 业务事件映射 → 本模块 ``AguiStreamTransformer``: 把内部流条目
//!   (``AguiStreamItem``, 等价 Python StreamOne)翻译为官方事件对象
//! - 传输 → SSE(axum), 每条 data 为 ``serde_json::to_string(&Event)``
//!
//! 事件语义速查:
//! - RUN_STARTED / RUN_FINISHED / RUN_ERROR  一次运行的起止与失败(必发首尾)
//! - STEP_STARTED / STEP_FINISHED            运行内具名步骤(此处 = 图节点)
//! - TEXT_MESSAGE_START/CONTENT/END          助手正文流(CONTENT 增量 delta 拼接)
//! - TOOL_CALL_START/ARGS/END/RESULT         工具调用(ARGS 为入参增量;
//!                                           1.0 起 START 不含 input 字段;
//!                                           RESULT 结构化结果 JSON, 自带 messageId)
//! - STATE_SNAPSHOT                          全量状态快照(RUN_STARTED 后随发)
//! - REASONING_*                             推理过程流(按 message_id 分段)
//! - CUSTOM                                  协议扩展点, 业务自定义载荷(name 必填)
//!
//! 业务自定义 CUSTOM 事件名约定(命名空间.事件):
//! - rag.status         进度提示 { message, node }
//! - rag.intent_result  意图分析结构化结论
//! - rag.interaction    用户交互请求卡片(澄清/知识缺口补充)

use serde_json::{json, Map, Value};

// ── 官方事件模型(re-export 供 service/controller 层直接构造) ──
pub use ag_ui_protocol::{
    BaseEvent, CustomEvent, Event, ReasoningEndEvent, ReasoningMessageContentEvent,
    ReasoningMessageEndEvent, ReasoningMessageStartEvent, ReasoningStartEvent, RunErrorEvent,
    RunFinishedEvent, RunStartedEvent, StateSnapshotEvent, StepFinishedEvent, StepStartedEvent,
    TextMessageContentEvent, TextMessageEndEvent, TextMessageStartEvent, TextMessageRole,
    ToolCallArgsEvent, ToolCallEndEvent, ToolCallResultEvent, ToolCallStartEvent,
};

// 业务流事件类型 → AG-UI 的自定义事件名约定
pub const CUSTOM_NAME_STATUS: &str = "rag.status";
pub const CUSTOM_NAME_INTENT_RESULT: &str = "rag.intent_result";
pub const CUSTOM_NAME_INTERACTION: &str = "rag.interaction";

/// 生成 32 位 hex uuid(对齐 Python uuid4().hex)
fn new_id() -> String {
    uuid::Uuid::new_v4().simple().to_string()
}

/// 官方事件 → SSE data 载荷(JSON 字符串)
///
/// crate 序列化输出协议规定的 camelCase 字段(threadId/messageId/toolCallId/
/// stepName/...)并自动省略无值可选字段(不写 JSON null), 与 Python 官方 SDK
/// `model_dump_json(by_alias=True)` 逐字段一致。
pub fn encode_agui_event(event: impl Into<Event>) -> String {
    serde_json::to_string(&event.into()).unwrap_or_else(|_| "{}".to_string())
}

/// 紧凑中文安全 JSON 序列化(工具入参/结果载荷)
fn dumps(value: &Value) -> String {
    serde_json::to_string(value).unwrap_or_else(|_| "null".to_string())
}

/// 业务内部流条目(等价 Python StreamOne: content/node_name/stream_event_type/data)
///
/// 由调用方(RAG 问答/agent 聊天/直连 LLM 对话)在产出 token 的位置构造,
/// 经 ``AguiStreamTransformer`` 翻译为官方事件。
#[derive(Debug, Clone)]
pub enum AguiStreamItem {
    /// 状态更新(stream_event_type=status): 节点进度提示
    Status {
        /// 节点名
        node: String,
        /// 人话进度文案
        message: String,
    },
    /// 正式回答增量(answer): 正文消息流
    Answer { delta: String },
    /// 思考过程增量(llm_thinking / agent_thinking): 推理流, 按节点分段
    Reasoning {
        /// 节点名(分段 key)
        node: String,
        /// 思考增量
        delta: String,
    },
    /// 思考结论(agent_thinking_conclusion): 闭推理段 + 意图结构化结论
    ReasoningConclusion {
        /// 节点名(切换步骤用)
        node: String,
        /// 文本结论(填入 data.conclusion 兜底)
        conclusion: String,
        /// 结构化结论载荷
        data: Option<Value>,
    },
    /// 工具调用(tool_call): 检索入参走 ARGS 增量, 结构化 results 走 RESULT.content
    ToolCall {
        /// 节点名(tool_name 缺省时兜底)
        node: String,
        /// 工具名(缺省时 node → "knowledge_search")
        tool_name: Option<String>,
        /// 调用入参(JSON, 整体作为一条 ARGS 增量下发)
        request: Option<Value>,
        /// 结构化结果(JSON, 优先于文本 content)
        results: Option<Value>,
        /// 文本结果兜底
        content: String,
    },
    /// 用户交互请求(interaction): 澄清/知识缺口补充卡片
    Interaction {
        /// 交互问题文本(填入 data.question 兜底)
        question: String,
        /// 结构化交互载荷
        data: Option<Value>,
    },
    /// 错误(error): RUN_ERROR, 错误即运行终态
    Error { message: String },
}

impl AguiStreamItem {
    /// 从流事件字符串形态构造(等价 Python 的 stream_event_type 分发),
    /// 供现有以字符串标识事件类型的调用方(RAG/agent)复用; 未识别类型返回 None。
    pub fn from_stream_one(
        event_type: &str,
        node_name: &str,
        content: &str,
        data: Option<Value>,
    ) -> Option<Self> {
        let item = match event_type {
            "status" => Self::Status {
                node: node_name.to_string(),
                message: content.to_string(),
            },
            "answer" | "" | "None" => Self::Answer { delta: content.to_string() },
            "llm_thinking" | "agent_thinking" => Self::Reasoning {
                node: node_name.to_string(),
                delta: content.to_string(),
            },
            "agent_thinking_conclusion" => Self::ReasoningConclusion {
                node: node_name.to_string(),
                conclusion: content.to_string(),
                data,
            },
            "tool_call" => Self::ToolCall {
                node: node_name.to_string(),
                tool_name: data
                    .as_ref()
                    .and_then(|d| d.get("tool_name"))
                    .and_then(Value::as_str)
                    .map(str::to_string),
                request: data.as_ref().and_then(|d| d.get("request")).cloned(),
                results: data.as_ref().and_then(|d| d.get("results")).cloned(),
                content: content.to_string(),
            },
            "interaction" => Self::Interaction {
                question: content.to_string(),
                data,
            },
            "error" => Self::Error { message: content.to_string() },
            _ => return None,
        };
        Some(item)
    }
}

/// 把业务内部流翻译为官方 AG-UI 事件流的有状态转换器
///
/// 状态机职责(输入为 ``AguiStreamItem``, 输出为已编码 SSE 载荷字符串):
/// - 首条前发 RUN_STARTED(+可选 STATE_SNAPSHOT), 结束发 RUN_FINISHED / 出错发 RUN_ERROR
/// - Status(节点切换) → STEP_STARTED/STEP_FINISHED + CUSTOM(rag.status 进度提示)
/// - Answer → TEXT_MESSAGE_START/CONTENT/END(单条助手消息, 按 messageId 串联)
/// - Reasoning → REASONING_* 推理流(按节点分段, 段=reasoning message_id,
///   节点切换时先闭旧段再开新段)
/// - ReasoningConclusion → CUSTOM(rag.intent_result, 结构化意图结论)
/// - ToolCall → TOOL_CALL_START/ARGS/END/RESULT
/// - Interaction → CUSTOM(rag.interaction, 用户交互请求卡片)
/// - Error → RUN_ERROR
pub struct AguiStreamTransformer {
    /// threadId: AG-UI 会话线程(RAG 场景即 conversation_id); runId: 本次运行
    thread_id: String,
    run_id: String,
    initial_state: Option<Value>,
    // 运行状态标记(开闭分组的游标)
    message_id: Option<String>,
    reasoning_id: Option<String>,
    reasoning_key: Option<String>,
    current_step: Option<String>,
    errored: bool,
}

impl AguiStreamTransformer {
    /// 创建转换器; runId 即时分配(32 位 hex)
    pub fn new(thread_id: impl Into<String>) -> Self {
        Self {
            thread_id: thread_id.into(),
            run_id: new_id(),
            initial_state: None,
            message_id: None,
            reasoning_id: None,
            reasoning_key: None,
            current_step: None,
            errored: false,
        }
    }

    /// 附带初始状态(RUN_STARTED 后随发 STATE_SNAPSHOT 全量快照)
    pub fn with_initial_state(mut self, state: Value) -> Self {
        self.initial_state = Some(state);
        self
    }

    pub fn thread_id(&self) -> &str {
        &self.thread_id
    }

    pub fn run_id(&self) -> &str {
        &self.run_id
    }

    /// 是否已发过 RUN_ERROR(错误即运行终态, 调用方据此停止后续转换)
    pub fn errored(&self) -> bool {
        self.errored
    }

    /// 运行起始帧: RUN_STARTED(+可选 STATE_SNAPSHOT)
    pub fn start_frames(&self) -> Vec<String> {
        let mut frames = vec![encode_agui_event(RunStartedEvent {
            base: BaseEvent::default(),
            thread_id: self.thread_id.clone(),
            run_id: self.run_id.clone(),
            parent_run_id: None,
            input: None,
        })];
        if let Some(state) = &self.initial_state {
            frames.push(encode_agui_event(StateSnapshotEvent {
                base: BaseEvent::default(),
                snapshot: state.clone(),
            }));
        }
        frames
    }

    /// 处理一条业务流条目, 产出对应事件组(已编码 SSE 载荷)
    pub fn handle_item(&mut self, item: &AguiStreamItem) -> Vec<String> {
        let mut events: Vec<Event> = Vec::new();
        match item {
            AguiStreamItem::Status { node, message } => {
                // 节点进度: 步骤切换 + 人话提示
                self.open_step(&mut events, node);
                events.push(
                    CustomEvent {
                        base: BaseEvent::default(),
                        name: CUSTOM_NAME_STATUS.to_string(),
                        value: json!({ "message": message, "node": node }),
                    }
                    .into(),
                );
            }
            AguiStreamItem::Answer { delta } => {
                if !delta.is_empty() {
                    let message_id = self.open_message(&mut events);
                    events.push(
                        TextMessageContentEvent {
                            base: BaseEvent::default(),
                            message_id,
                            delta: delta.clone(),
                        }
                        .into(),
                    );
                }
            }
            AguiStreamItem::Reasoning { node, delta } => {
                if !delta.is_empty() {
                    let reasoning_id = self.open_reasoning(&mut events, node);
                    events.push(
                        ReasoningMessageContentEvent {
                            base: BaseEvent::default(),
                            message_id: reasoning_id,
                            delta: delta.clone(),
                        }
                        .into(),
                    );
                }
            }
            AguiStreamItem::ReasoningConclusion { node, conclusion, data } => {
                // data(缺 conclusion 键时)以文本结论兜底
                let mut map = match data {
                    Some(Value::Object(m)) => m.clone(),
                    _ => Map::new(),
                };
                map.entry("conclusion".to_string())
                    .or_insert_with(|| json!(conclusion));
                self.close_reasoning(&mut events);
                self.open_step(&mut events, node);
                events.push(
                    CustomEvent {
                        base: BaseEvent::default(),
                        name: CUSTOM_NAME_INTENT_RESULT.to_string(),
                        value: Value::Object(map),
                    }
                    .into(),
                );
            }
            AguiStreamItem::ToolCall { node, tool_name, request, results, content } => {
                let tool_call_id = new_id();
                let tool_name = tool_name
                    .as_deref()
                    .filter(|s| !s.is_empty())
                    .or_else(|| (!node.is_empty()).then_some(node.as_str()))
                    .unwrap_or("knowledge_search");
                events.push(
                    ToolCallStartEvent {
                        base: BaseEvent::default(),
                        tool_call_id: tool_call_id.clone(),
                        tool_call_name: tool_name.to_string(),
                        parent_message_id: None,
                    }
                    .into(),
                );
                // AG-UI 1.0 的 START 不含 input 字段: 调用入参作为 ARGS 增量下发
                if let Some(request) = request {
                    events.push(
                        ToolCallArgsEvent {
                            base: BaseEvent::default(),
                            tool_call_id: tool_call_id.clone(),
                            delta: dumps(request),
                        }
                        .into(),
                    );
                }
                events.push(
                    ToolCallEndEvent {
                        base: BaseEvent::default(),
                        tool_call_id: tool_call_id.clone(),
                    }
                    .into(),
                );
                // RESULT: 结构化 results 优先(前端直接消费引用溯源), 回退格式化文本
                let result_content = match results {
                    Some(results) => dumps(results),
                    None => content.clone(),
                };
                events.push(
                    ToolCallResultEvent {
                        base: BaseEvent::default(),
                        message_id: new_id(),
                        tool_call_id,
                        content: result_content,
                        role: None,
                    }
                    .into(),
                );
            }
            AguiStreamItem::Interaction { question, data } => {
                // data(缺 question 键时)以问题文本兜底
                let mut map = match data {
                    Some(Value::Object(m)) => m.clone(),
                    _ => Map::new(),
                };
                map.entry("question".to_string()).or_insert_with(|| json!(question));
                events.push(
                    CustomEvent {
                        base: BaseEvent::default(),
                        name: CUSTOM_NAME_INTERACTION.to_string(),
                        value: Value::Object(map),
                    }
                    .into(),
                );
            }
            AguiStreamItem::Error { message } => {
                self.errored = true;
                events.push(
                    RunErrorEvent {
                        base: BaseEvent::default(),
                        message: if message.is_empty() { "未知错误".to_string() } else { message.clone() },
                        code: None,
                    }
                    .into(),
                );
            }
        }
        events.into_iter().map(encode_agui_event).collect()
    }

    /// 正常收尾帧: 关闭未闭的推理段/正文消息/步骤, 最后 RUN_FINISHED;
    /// 已发 RUN_ERROR 则不再发任何收尾(协议: 错误即运行终态)
    pub fn finalize(&mut self) -> Vec<String> {
        if self.errored {
            return Vec::new();
        }
        let mut events: Vec<Event> = Vec::new();
        self.close_reasoning(&mut events);
        if let Some(message_id) = self.message_id.take() {
            events.push(
                TextMessageEndEvent {
                    base: BaseEvent::default(),
                    message_id,
                }
                .into(),
            );
        }
        if let Some(step) = self.current_step.take() {
            events.push(
                StepFinishedEvent {
                    base: BaseEvent::default(),
                    step_name: step,
                }
                .into(),
            );
        }
        events.push(
            RunFinishedEvent {
                base: BaseEvent::default(),
                thread_id: self.thread_id.clone(),
                run_id: self.run_id.clone(),
                result: None,
                outcome: None,
            }
            .into(),
        );
        events.into_iter().map(encode_agui_event).collect()
    }

    /// 转换器外部错误兜底(等价 Python transform 的 except 分支):
    /// 置错误态并发 RUN_ERROR; 已错误则不重复发
    pub fn fail(&mut self, message: impl Into<String>) -> Vec<String> {
        if self.errored {
            return Vec::new();
        }
        self.errored = true;
        vec![encode_agui_event(RunErrorEvent {
            base: BaseEvent::default(),
            message: message.into(),
            code: None,
        })]
    }

    // ── 开闭分组(游标管理) ──────────────────────

    /// 切换具名步骤: 先闭旧步骤(STEP_FINISHED)再开新步骤(STEP_STARTED)
    fn open_step(&mut self, events: &mut Vec<Event>, step_name: &str) {
        if step_name.is_empty() || Some(step_name) == self.current_step.as_deref() {
            return;
        }
        if let Some(step) = self.current_step.take() {
            events.push(
                StepFinishedEvent {
                    base: BaseEvent::default(),
                    step_name: step,
                }
                .into(),
            );
        }
        self.current_step = Some(step_name.to_string());
        events.push(
            StepStartedEvent {
                base: BaseEvent::default(),
                step_name: step_name.to_string(),
            }
            .into(),
        );
    }

    /// 惰性开启正文消息(TEXT_MESSAGE_START), 全程单条消息
    fn open_message(&mut self, events: &mut Vec<Event>) -> String {
        if self.message_id.is_none() {
            self.message_id = Some(new_id());
            events.push(
                TextMessageStartEvent {
                    base: BaseEvent::default(),
                    message_id: self.message_id.clone().unwrap(),
                    role: TextMessageRole::Assistant,
                    name: None,
                }
                .into(),
            );
        }
        self.message_id.clone().unwrap()
    }

    /// 按节点开启推理段: REASONING_START + REASONING_MESSAGE_START
    fn open_reasoning(&mut self, events: &mut Vec<Event>, node_name: &str) -> String {
        let key = if node_name.is_empty() { "default" } else { node_name }.to_string();
        if self.reasoning_id.is_some() && Some(&key) == self.reasoning_key.as_ref() {
            return self.reasoning_id.clone().unwrap();
        }
        self.close_reasoning(events);
        let id = new_id();
        self.reasoning_id = Some(id.clone());
        self.reasoning_key = Some(key);
        events.push(
            ReasoningStartEvent {
                base: BaseEvent::default(),
                message_id: id.clone(),
            }
            .into(),
        );
        events.push(
            ReasoningMessageStartEvent {
                base: BaseEvent::default(),
                message_id: id.clone(),
                role: Default::default(),
            }
            .into(),
        );
        id
    }

    /// 关闭当前推理段: REASONING_MESSAGE_END + REASONING_END
    fn close_reasoning(&mut self, events: &mut Vec<Event>) {
        let Some(id) = self.reasoning_id.take() else {
            return;
        };
        self.reasoning_key = None;
        events.push(
            ReasoningMessageEndEvent {
                base: BaseEvent::default(),
                message_id: id.clone(),
            }
            .into(),
        );
        events.push(
            ReasoningEndEvent {
                base: BaseEvent::default(),
                message_id: id,
            }
            .into(),
        );
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn start_and_finish_wire_format() {
        let mut t = AguiStreamTransformer::new("conv-1");
        let frames = t.start_frames();
        assert_eq!(frames.len(), 1);
        assert!(frames[0].contains(r#""type":"RUN_STARTED""#));
        assert!(frames[0].contains(r#""threadId":"conv-1""#));
        assert!(!frames[0].contains("timestamp")); // None 字段省略

        let frames = t.finalize();
        assert_eq!(frames.len(), 1);
        assert!(frames[0].contains(r#""type":"RUN_FINISHED""#));
        // Python 官方 SDK: outcome 缺省即 success, 不写 null
        assert!(!frames[0].contains("outcome"));
    }

    #[test]
    fn state_snapshot_follows_run_started() {
        let t = AguiStreamTransformer::new("conv-1").with_initial_state(json!({
            "conversationId": "conv-1", "deepThinking": true
        }));
        let frames = t.start_frames();
        assert_eq!(frames.len(), 2);
        assert!(frames[1].contains(r#""type":"STATE_SNAPSHOT""#));
        assert!(frames[1].contains(r#""deepThinking":true"#));
    }

    #[test]
    fn status_switches_steps_with_custom_event() {
        let mut t = AguiStreamTransformer::new("c");
        let frames = t.handle_item(&AguiStreamItem::Status {
            node: "intent_analysis".into(),
            message: "正在分析意图…".into(),
        });
        // STEP_STARTED + CUSTOM
        assert_eq!(frames.len(), 2);
        assert!(frames[0].contains(r#""type":"STEP_STARTED""#));
        assert!(frames[1].contains(r#""name":"rag.status""#));
        assert!(frames[1].contains("正在分析意图"));

        // 同节点重复 status: 不重复切步
        let frames = t.handle_item(&AguiStreamItem::Status {
            node: "intent_analysis".into(),
            message: "again".into(),
        });
        assert_eq!(frames.len(), 1);

        // 节点切换: 闭旧步开新步
        let frames = t.handle_item(&AguiStreamItem::Status {
            node: "chat".into(),
            message: "正在生成回答…".into(),
        });
        assert_eq!(frames.len(), 3);
        assert!(frames[0].contains(r#""type":"STEP_FINISHED""#));
        assert!(frames[1].contains(r#""type":"STEP_STARTED""#));
    }

    #[test]
    fn answer_single_message_lifecycle() {
        let mut t = AguiStreamTransformer::new("c");
        let frames = t.handle_item(&AguiStreamItem::Answer { delta: "你好".into() });
        assert_eq!(frames.len(), 2);
        assert!(frames[0].contains(r#""type":"TEXT_MESSAGE_START""#));
        assert!(frames[0].contains(r#""role":"assistant""#));
        assert!(frames[1].contains(r#""delta":"你好""#));
        let start: Value = serde_json::from_str(&frames[0]).unwrap();

        let frames = t.handle_item(&AguiStreamItem::Answer { delta: "".into() });
        assert!(frames.is_empty()); // 空 delta 不发帧

        // finalize: TEXT_MESSAGE_END + RUN_FINISHED, 与 START 同一 messageId
        let frames = t.finalize();
        assert_eq!(frames.len(), 2);
        let end: Value = serde_json::from_str(&frames[0]).unwrap();
        assert_eq!(start["messageId"], end["messageId"]);
        assert!(frames[1].contains("RUN_FINISHED"));
    }

    #[test]
    fn reasoning_segments_by_node() {
        let mut t = AguiStreamTransformer::new("c");
        let f1 = t.handle_item(&AguiStreamItem::Reasoning { node: "chat".into(), delta: "想".into() });
        // REASONING_START + REASONING_MESSAGE_START + CONTENT
        assert_eq!(f1.len(), 3);

        // 同节点继续: 仅 CONTENT
        let f2 = t.handle_item(&AguiStreamItem::Reasoning { node: "chat".into(), delta: "考".into() });
        assert_eq!(f2.len(), 1);

        // 结论: 闭段 + 切步 + CUSTOM(rag.intent_result)
        let f3 = t.handle_item(&AguiStreamItem::ReasoningConclusion {
            node: "chat".into(),
            conclusion: "检索".into(),
            data: Some(json!({"intent": "search"})),
        });
        // REASONING_MESSAGE_END + REASONING_END + STEP_STARTED + CUSTOM
        assert_eq!(f3.len(), 4);
        assert!(f3[3].contains(r#""name":"rag.intent_result""#));
        assert!(f3[3].contains(r#""conclusion":"检索""#));
        // 已有 intent 时不覆盖 data 字段, conclusion 兜底仍写入
        assert!(f3[3].contains(r#""intent":"search""#));
    }

    #[test]
    fn tool_call_full_group() {
        let mut t = AguiStreamTransformer::new("c");
        let frames = t.handle_item(&AguiStreamItem::ToolCall {
            node: "knowledge_search".into(),
            tool_name: None,
            request: Some(json!({"query": "量子"})),
            results: Some(json!([{"id": 1}])),
            content: "命中1条".into(),
        });
        // START + ARGS + END + RESULT
        assert_eq!(frames.len(), 4);
        assert!(frames[0].contains(r#""toolCallName":"knowledge_search""#));
        assert!(frames[1].contains(r#""delta":"{\"query\":\"量子\"}""#));
        assert!(frames[3].contains(r#""type":"TOOL_CALL_RESULT""#));
        assert!(frames[3].contains(r#""content":"[{\"id\":1}]""#));

        // results 缺省回退文本 content
        let frames = t.handle_item(&AguiStreamItem::ToolCall {
            node: String::new(),
            tool_name: None,
            request: None,
            results: None,
            content: "纯文本结果".into(),
        });
        assert!(frames[2].contains("纯文本结果"));
    }

    #[test]
    fn error_is_terminal_state() {
        let mut t = AguiStreamTransformer::new("c");
        t.handle_item(&AguiStreamItem::Answer { delta: "部分".into() });
        let frames = t.handle_item(&AguiStreamItem::Error { message: String::new() });
        assert_eq!(frames.len(), 1);
        assert!(frames[0].contains(r#""type":"RUN_ERROR""#));
        assert!(frames[0].contains("未知错误")); // 空消息兜底文案
        assert!(t.errored());

        // 错误后: finalize 不发任何收尾, fail 不重复发
        assert!(t.finalize().is_empty());
        assert!(t.fail("again").is_empty());
    }

    #[test]
    fn from_stream_one_dispatch() {
        let item = AguiStreamItem::from_stream_one("answer", "chat", "文本", None).unwrap();
        assert!(matches!(item, AguiStreamItem::Answer { .. }));

        let item = AguiStreamItem::from_stream_one("status", "intent_analysis", "提示", None).unwrap();
        assert!(matches!(item, AguiStreamItem::Status { .. }));

        let item = AguiStreamItem::from_stream_one(
            "tool_call",
            "knowledge_search",
            "结果",
            Some(json!({"tool_name": "kb", "request": {"q": 1}, "results": []})),
        )
        .unwrap();
        match item {
            AguiStreamItem::ToolCall { tool_name, request, results, .. } => {
                assert_eq!(tool_name.as_deref(), Some("kb"));
                assert_eq!(request, Some(json!({"q": 1})));
                assert_eq!(results, Some(json!([])));
            }
            _ => panic!("应分发为 ToolCall"),
        }

        assert!(AguiStreamItem::from_stream_one("unknown_type", "", "", None).is_none());
    }
}
