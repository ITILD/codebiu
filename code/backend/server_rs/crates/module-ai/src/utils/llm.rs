//! LLM REST 调用层(等价 Python utils/llm/factory/builder.py + utils/llm/stream)
//!
//! Python 侧经 LangChain 构建模型实例, Rust 侧直接以 HTTP 协议调用:
//! - chat: openai/dashscope 走 `{url}/chat/completions`, ollama 走 `{url}/api/chat`
//! - embeddings: openai/dashscope 走 `{url}/embeddings`, ollama 走 `{url}/api/embed`
//! - vllm/aws: 未实现, 调用即报错(文案对齐 Python 工厂 ValueError, HTTP 层映射 404)
//!
//! 流式: openai 兼容 SSE(`data: {...}` / `data: [DONE]`)与 ollama NDJSON 双解析,
//! 事件组装对齐 stream/schemas.py 的 StreamChunkResponse(start/chunk 共用 response_id,
//! end/error 使用新 uuid, timestamp 恒 0.0)。
//!
//! 思考模式: openai/dashscope 请求体携带 `enable_thinking`(= !no_think);
//! "始终思考"模型(如 GLM 系)关闭思考被拒(400 文案含"不支持关闭思考")时,
//! 登记注册表并自动以开启思考重试(对齐 ChatQwenWithReasoning 回退逻辑)。

use std::collections::HashSet;
use std::sync::{Mutex, OnceLock};
use std::time::Duration;

use serde::Serialize;
use serde_json::{json, Value};
use tokio::sync::mpsc;

use common::utils::error::AppError;

use crate::do_::llm::Message;
use crate::do_::model_config::ModelConfigCreateRequest;

// ############################# SSE 事件模型(对齐 stream/schemas.py) #############################

/// 流式响应状态(对齐 StreamStatus 枚举: start/stream/end/error)
#[derive(Debug, Clone, Copy, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum StreamStatus {
    Start,
    Stream,
    End,
    Error,
}

/// SSE 流式响应单 Chunk(字段与 Python StreamChunkResponse 同构, None 序列化为 null)
#[derive(Debug, Clone, Serialize)]
pub struct StreamChunkResponse {
    pub status: StreamStatus,
    pub role: &'static str,
    pub content: Option<String>,
    pub response_id: String,
    pub timestamp: f64,
    pub node_name: Option<String>,
    pub stream_event_type: Option<String>,
}

/// 生成 32 位 hex uuid(对齐 Python uuid4().hex)
fn new_response_id() -> String {
    uuid::Uuid::new_v4().simple().to_string()
}

impl StreamChunkResponse {
    /// start 事件(开启一条新响应流, 分配新 response_id)
    pub fn start() -> Self {
        Self {
            status: StreamStatus::Start,
            role: "assistant",
            content: None,
            response_id: new_response_id(),
            timestamp: 0.0,
            node_name: None,
            stream_event_type: None,
        }
    }

    /// 内容 chunk 事件(复用 start 事件的 response_id)
    pub fn chunk(response_id: &str, content: impl Into<String>) -> Self {
        Self {
            status: StreamStatus::Stream,
            role: "assistant",
            content: Some(content.into()),
            response_id: response_id.to_string(),
            timestamp: 0.0,
            node_name: None,
            stream_event_type: None,
        }
    }

    /// end 事件(新 response_id)
    pub fn end() -> Self {
        Self {
            status: StreamStatus::End,
            role: "assistant",
            content: None,
            response_id: new_response_id(),
            timestamp: 0.0,
            node_name: None,
            stream_event_type: None,
        }
    }

    /// error 事件(新 response_id, content 携带错误文案)
    pub fn error(msg: impl Into<String>) -> Self {
        Self {
            status: StreamStatus::Error,
            role: "assistant",
            content: Some(msg.into()),
            response_id: new_response_id(),
            timestamp: 0.0,
            node_name: None,
            stream_event_type: None,
        }
    }

    /// 序列化为 SSE data 载荷(含 null 字段, 对齐 model_dump_json)
    pub fn to_json(&self) -> String {
        serde_json::to_string(self).unwrap_or_else(|_| "{}".to_string())
    }
}

// ############################# 调用目标(对齐 builder.build_model 的参数读取) #############################

/// LLM 调用目标: 从模型配置实体或创建请求提取的调用参数
#[derive(Debug, Clone)]
pub struct LlmTarget {
    pub model_type: String,
    pub server_type: String,
    pub model: String,
    pub url: String,
    pub api_key: Option<String>,
    pub temperature: f64,
    pub timeout: i32,
    pub no_think: bool,
    pub out_tokens: i32,
}

/// 按 server_type 补默认 url(与 do/model_config.rs apply_default_url 保持一致)
pub fn default_url_for(server_type: &str) -> &'static str {
    match server_type {
        "dashscope" => "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "vllm" => "http://localhost:8000/v1",
        "aws" => "https://bedrock-runtime.us-east-1.amazonaws.com",
        "ollama" => "http://localhost:11434",
        // openai 及其他未知方案回落官方地址
        _ => "https://api.openai.com/v1",
    }
}

impl LlmTarget {
    /// 从模型配置实体构建(建库后的模型实例缓存/对话调用用)
    pub fn from_entity(m: &crate::do_::entity::model_config::Model) -> Self {
        Self {
            model_type: m.model_type.clone(),
            server_type: m.server_type.clone(),
            model: m.model.clone(),
            url: m
                .url
                .clone()
                .unwrap_or_else(|| default_url_for(&m.server_type).to_string()),
            api_key: m.api_key.clone(),
            temperature: m.temperature.unwrap_or(0.7),
            timeout: m.timeout.unwrap_or(60),
            no_think: m.no_think.unwrap_or(false),
            out_tokens: m.out_tokens.unwrap_or(8192),
        }
    }

    /// 从创建请求构建(check-config 用; url 缺失时按方案补默认值)
    pub fn from_create_request(req: &ModelConfigCreateRequest) -> Self {
        Self {
            model_type: req.model_type.clone(),
            server_type: req.server_type.clone(),
            model: req.model.clone(),
            url: req
                .url
                .clone()
                .unwrap_or_else(|| default_url_for(&req.server_type).to_string()),
            api_key: req.api_key.clone(),
            temperature: req.temperature,
            timeout: req.timeout,
            no_think: req.no_think.unwrap_or(false),
            out_tokens: req.out_tokens,
        }
    }

    /// 是否 OpenAI 兼容协议(openai/dashscope)
    pub fn is_openai_compatible(&self) -> bool {
        matches!(self.server_type.as_str(), "openai" | "dashscope")
    }

    /// 是否 Ollama 本地协议
    pub fn is_ollama(&self) -> bool {
        self.server_type == "ollama"
    }
}

// ############################# "始终思考"模型注册表(对齐 think.py) #############################

/// 已确认始终思考的模型注册表(key=(url, model)): 命中后不再尝试关闭思考
static ALWAYS_THINK_MODELS: OnceLock<Mutex<HashSet<(String, String)>>> = OnceLock::new();

fn always_think_registry() -> &'static Mutex<HashSet<(String, String)>> {
    ALWAYS_THINK_MODELS.get_or_init(|| Mutex::new(HashSet::new()))
}

/// 识别"该模型始终思考, 不支持关闭思考"类 400 错误(对齐 _ALWAYS_THINK_HINT)
fn is_always_think_error(msg: &str) -> bool {
    msg.contains("不支持关闭思考")
}

/// 当前配置是否要求关闭思考(no_think=true → enable_thinking=false)
fn wants_think_off(target: &LlmTarget) -> bool {
    target.is_openai_compatible() && target.no_think
}

/// 初始 enable_thinking 取值: 已登记的始终思考模型直接开启思考
fn initial_enable_thinking(target: &LlmTarget) -> Option<bool> {
    if !target.is_openai_compatible() {
        return None;
    }
    if wants_think_off(target) {
        let key = (target.url.clone(), target.model.clone());
        let registered = always_think_registry()
            .lock()
            .expect("思考注册表锁")
            .contains(&key);
        // 已确认始终思考的模型跳过关闭思考, 直接开启
        Some(registered)
    } else {
        Some(true)
    }
}

// ############################# 请求构造与发送 #############################

/// 消息角色转 REST 请求字符串(human/ai 为 langchain 别名, 正常入口已在 DTO 层归一化)
fn wire_role(m: &Message) -> &'static str {
    match m.role.as_str() {
        "human" | "user" => "user",
        "ai" | "assistant" => "assistant",
        _ => "system",
    }
}

/// 消息列表 → REST 请求消息数组([{role, content}])
fn wire_messages(messages: &[Message]) -> Value {
    Value::Array(
        messages
            .iter()
            .map(|m| json!({"role": wire_role(m), "content": m.content}))
            .collect(),
    )
}

/// 校验 chat 方案可用性(等价 build_chat_model 的 ValueError, 文案一致)
pub fn ensure_chat_supported(target: &LlmTarget) -> Result<(), AppError> {
    if target.is_openai_compatible() || target.is_ollama() {
        Ok(())
    } else {
        Err(AppError::not_found(format!(
            "服务方案 {} 的对话模型暂未实现",
            target.server_type
        )))
    }
}

/// 发送 chat 请求(openai 兼容 / ollama 双协议), 仅校验 HTTP 状态, 响应体由调用方解析
///
/// 非流式请求设置总超时(取配置 timeout 秒); 流式请求不设总超时(由专用客户端的
/// read_timeout 兜底空闲连接), 避免长回答被切断。
async fn send_chat_request(
    http: &reqwest::Client,
    target: &LlmTarget,
    messages: &Value,
    stream: bool,
    enable_thinking: Option<bool>,
) -> Result<reqwest::Response, AppError> {
    let (url, body) = if target.is_ollama() {
        (
            format!("{}/api/chat", target.url.trim_end_matches('/')),
            json!({
                "model": target.model,
                "messages": messages,
                "stream": stream,
                "options": {"temperature": target.temperature},
            }),
        )
    } else {
        let mut body = json!({
            "model": target.model,
            "messages": messages,
            "temperature": target.temperature,
            "stream": stream,
        });
        // extra_body 字段直传请求体顶层(对齐 ChatQwenWithReasoning extra_body)
        if let Some(flag) = enable_thinking {
            body["enable_thinking"] = json!(flag);
        }
        (
            format!("{}/chat/completions", target.url.trim_end_matches('/')),
            body,
        )
    };
    let mut req = http.post(&url).json(&body);
    if !stream {
        req = req.timeout(Duration::from_secs(target.timeout.max(1) as u64));
    }
    if let Some(key) = target.api_key.as_deref().filter(|k| !k.is_empty()) {
        req = req.bearer_auth(key);
    }
    let resp = req
        .send()
        .await
        .map_err(|e| AppError::internal(format!("模型请求失败: {e}")))?;
    let status = resp.status();
    if status.is_client_error() || status.is_server_error() {
        let body_text = resp.text().await.unwrap_or_default();
        // 错误文案格式对齐 openai SDK("Error code: 400 - {...}"), 供思考回退逻辑做子串匹配
        return Err(AppError::internal(format!(
            "Error code: {} - {}",
            status.as_u16(),
            super::truncate_body(&body_text)
        )));
    }
    Ok(resp)
}

/// 发送请求并在"始终思考模型不支持关闭思考"时自动回退开启思考重试(对齐 ChatQwenWithReasoning)
async fn send_chat_with_think_fallback(
    http: &reqwest::Client,
    target: &LlmTarget,
    messages: &Value,
    stream: bool,
    enable_thinking: &mut Option<bool>,
) -> Result<reqwest::Response, AppError> {
    loop {
        match send_chat_request(http, target, messages, stream, *enable_thinking).await {
            Ok(resp) => return Ok(resp),
            Err(e) => {
                let msg = e.to_string();
                if wants_think_off(target) && is_always_think_error(&msg) {
                    let key = (target.url.clone(), target.model.clone());
                    // 首次命中才登记并重试, 避免死循环
                    let first_hit = always_think_registry()
                        .lock()
                        .expect("思考注册表锁")
                        .insert(key);
                    if first_hit {
                        tracing::warn!(
                            "模型始终思考不支持关闭思考({}/{}), 已改用开启思考重试",
                            target.url,
                            target.model
                        );
                        *enable_thinking = Some(true);
                        continue;
                    }
                }
                return Err(e);
            }
        }
    }
}

/// 从 chat 响应提取 content(openai: choices[0].message.content / ollama: message.content)
fn extract_chat_content(payload: &Value) -> Value {
    payload
        .pointer("/choices/0/message/content")
        .or_else(|| payload.pointer("/message/content"))
        .cloned()
        .unwrap_or(Value::String(String::new()))
}

/// 非流式对话: 返回模型 content(字符串或分段数组, 与 OpenAI 响应同形)
pub async fn chat_once(
    http: &reqwest::Client,
    target: &LlmTarget,
    messages: &[Message],
) -> Result<Value, AppError> {
    chat_once_raw(http, target, wire_messages(messages)).await
}

/// 原始消息体非流式对话(供多模态等特殊 content 结构使用, messages 为 OpenAI 消息数组)
pub async fn chat_once_raw(
    http: &reqwest::Client,
    target: &LlmTarget,
    messages: Value,
) -> Result<Value, AppError> {
    ensure_chat_supported(target)?;
    let mut enable_thinking = initial_enable_thinking(target);
    let resp =
        send_chat_with_think_fallback(http, target, &messages, false, &mut enable_thinking).await?;
    let text = resp
        .text()
        .await
        .map_err(|e| AppError::internal(format!("模型响应读取失败: {e}")))?;
    let payload: Value = serde_json::from_str(&text)
        .map_err(|e| AppError::internal(format!("模型响应解析失败: {e}")))?;
    Ok(extract_chat_content(&payload))
}

// ############################# 流式对话(SSE/NDJSON 双协议) #############################

/// 流式请求专用 HTTP 客户端(无总超时, 空闲读超时 300s 兜底挂死连接)
fn stream_http() -> &'static reqwest::Client {
    static CLIENT: OnceLock<reqwest::Client> = OnceLock::new();
    CLIENT.get_or_init(|| {
        reqwest::Client::builder()
            .connect_timeout(Duration::from_secs(15))
            .read_timeout(Duration::from_secs(300))
            .build()
            .expect("LLM 流式 HTTP 客户端构建失败")
    })
}

/// 单行流式数据的解析结果
enum StreamLine {
    /// 注释/心跳等无意义行
    Ignore,
    /// 内容片段(可能为空串: 角色帧/finish_reason 帧)
    Content(String),
    /// 流结束(data: [DONE] 或 ollama done=true)
    Done,
}

/// 解析单行流式数据(openai SSE data 行与 ollama NDJSON 行统一处理)
fn parse_stream_line(line: &str) -> StreamLine {
    let line = line.trim();
    if line.is_empty() || line.starts_with(':') {
        return StreamLine::Ignore;
    }
    // openai 兼容 SSE: "data: {...}" / "data: [DONE]"; ollama NDJSON 直接是 JSON 行
    let payload = line.strip_prefix("data:").map(str::trim).unwrap_or(line);
    if payload == "[DONE]" {
        return StreamLine::Done;
    }
    let Ok(value) = serde_json::from_str::<Value>(payload) else {
        return StreamLine::Ignore;
    };
    // ollama 结束帧: {"done": true, ...}
    if value.get("done") == Some(&Value::Bool(true)) {
        return StreamLine::Done;
    }
    let content = value
        .pointer("/choices/0/delta/content")
        .or_else(|| value.pointer("/message/content"))
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();
    StreamLine::Content(content)
}

/// 流式对话: 启动后台任务解析 SSE/NDJSON, 经通道返回内容片段
///
/// - Err 项对应建连失败或中途异常(调用方转为 SSE error 事件后终止)
/// - 建连阶段的"方案未实现"错误在本函数同步返回(调用方映射 404)
pub fn chat_stream(
    target: LlmTarget,
    messages: &[Message],
) -> Result<mpsc::Receiver<Result<String, AppError>>, AppError> {
    ensure_chat_supported(&target)?;
    let messages = wire_messages(messages);
    let (tx, rx) = mpsc::channel::<Result<String, AppError>>(64);
    tokio::spawn(async move {
        let http = stream_http();
        let mut enable_thinking = initial_enable_thinking(&target);
        let mut response = match send_chat_with_think_fallback(
            http,
            &target,
            &messages,
            true,
            &mut enable_thinking,
        )
        .await
        {
            Ok(r) => r,
            Err(e) => {
                let _ = tx.send(Err(e)).await;
                return;
            }
        };
        // 按行缓冲解析(SSE 与 NDJSON 均为行协议)
        let mut buffer = String::new();
        loop {
            match response.chunk().await {
                Ok(Some(bytes)) => {
                    buffer.push_str(&String::from_utf8_lossy(&bytes));
                    while let Some(pos) = buffer.find('\n') {
                        let line: String = buffer.drain(..=pos).collect();
                        match parse_stream_line(line.trim_end()) {
                            StreamLine::Ignore => {}
                            StreamLine::Content(text) => {
                                if !text.is_empty() && tx.send(Ok(text)).await.is_err() {
                                    // 接收端已关闭(客户端断开), 终止拉流
                                    return;
                                }
                            }
                            StreamLine::Done => return,
                        }
                    }
                }
                Ok(None) => break,
                Err(e) => {
                    let _ = tx
                        .send(Err(AppError::internal(format!("模型流式响应中断: {e}"))))
                        .await;
                    return;
                }
            }
        }
        // 冲刷无换行结尾的残余行
        if !buffer.trim().is_empty() {
            if let StreamLine::Content(text) = parse_stream_line(buffer.trim()) {
                if !text.is_empty() {
                    let _ = tx.send(Ok(text)).await;
                }
            }
        }
    });
    Ok(rx)
}

// ############################# 向量化(对齐 build_embeddings) #############################

/// 校验 embeddings 方案可用性(等价 build_embeddings 的 ValueError, 文案一致)
pub fn ensure_embeddings_supported(target: &LlmTarget) -> Result<(), AppError> {
    if target.is_openai_compatible() || target.is_ollama() {
        Ok(())
    } else {
        Err(AppError::not_found(format!(
            "服务方案 {} 的向量化模型暂未实现",
            target.server_type
        )))
    }
}

/// 向量化调用: 返回与输入顺序一致的向量列表
///
/// - openai/dashscope: `{url}/embeddings`(jina-embeddings 模型不传 dimensions, 对齐工厂逻辑)
/// - ollama: `{url}/api/embed`
pub async fn embed(
    http: &reqwest::Client,
    target: &LlmTarget,
    texts: &[String],
) -> Result<Vec<Vec<f64>>, AppError> {
    ensure_embeddings_supported(target)?;
    let (url, body) = if target.is_ollama() {
        (
            format!("{}/api/embed", target.url.trim_end_matches('/')),
            json!({"model": target.model, "input": texts}),
        )
    } else {
        let mut body = json!({"model": target.model, "input": texts});
        if !target.model.contains("jina-embeddings") {
            // 向量化模型的 out_tokens 语义为维度
            body["dimensions"] = json!(target.out_tokens);
        }
        (
            format!("{}/embeddings", target.url.trim_end_matches('/')),
            body,
        )
    };
    let mut req = http
        .post(&url)
        .json(&body)
        .timeout(Duration::from_secs(target.timeout.max(1) as u64));
    if let Some(key) = target.api_key.as_deref().filter(|k| !k.is_empty()) {
        req = req.bearer_auth(key);
    }
    let resp = req
        .send()
        .await
        .map_err(|e| AppError::internal(format!("向量化请求失败: {e}")))?;
    let status = resp.status();
    let text = resp
        .text()
        .await
        .map_err(|e| AppError::internal(format!("向量化响应读取失败: {e}")))?;
    if status.is_client_error() || status.is_server_error() {
        return Err(AppError::internal(format!(
            "Error code: {} - {}",
            status.as_u16(),
            super::truncate_body(&text)
        )));
    }
    let payload: Value = serde_json::from_str(&text)
        .map_err(|e| AppError::internal(format!("向量化响应解析失败: {e}")))?;
    // ollama: {"embeddings": [[...], ...]}
    if let Some(list) = payload.get("embeddings").and_then(Value::as_array) {
        return Ok(list
            .iter()
            .filter_map(|v| v.as_array())
            .map(|arr| arr.iter().filter_map(Value::as_f64).collect())
            .collect());
    }
    // openai: {"data": [{"index": 0, "embedding": [...]}]} 按 index 还原输入顺序
    if let Some(data) = payload.get("data").and_then(Value::as_array) {
        let mut pairs: Vec<(usize, Vec<f64>)> = data
            .iter()
            .filter_map(|item| {
                let index = item.get("index").and_then(Value::as_i64)?;
                let embedding = item.get("embedding").and_then(Value::as_array)?;
                Some((
                    index.max(0) as usize,
                    embedding.iter().filter_map(Value::as_f64).collect(),
                ))
            })
            .collect();
        pairs.sort_by_key(|(i, _)| *i);
        return Ok(pairs.into_iter().map(|(_, v)| v).collect());
    }
    Err(AppError::internal(format!(
        "向量化响应格式无法解析: {}",
        super::truncate_body(&payload.to_string())
    )))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn 流式事件字段与python契约同构() {
        let start = StreamChunkResponse::start();
        let start_json: Value = serde_json::from_str(&start.to_json()).expect("JSON 解析");
        assert_eq!(start_json["status"], "start");
        assert_eq!(start_json["role"], "assistant");
        assert_eq!(start_json["content"], Value::Null);
        assert_eq!(start_json["timestamp"], 0.0);
        assert_eq!(start_json["response_id"].as_str().expect("hex").len(), 32);

        let chunk = StreamChunkResponse::chunk(&start.response_id, "你好");
        let chunk_json: Value = serde_json::from_str(&chunk.to_json()).expect("JSON 解析");
        assert_eq!(chunk_json["status"], "stream");
        assert_eq!(chunk_json["response_id"], start_json["response_id"]);
        assert_eq!(chunk_json["content"], "你好");
        assert_eq!(chunk_json["node_name"], Value::Null);

        let end_json: Value =
            serde_json::from_str(&StreamChunkResponse::end().to_json()).expect("JSON 解析");
        assert_eq!(end_json["status"], "end");
        assert_ne!(end_json["response_id"], start_json["response_id"]);

        let err_json: Value = serde_json::from_str(&StreamChunkResponse::error("boom").to_json())
            .expect("JSON 解析");
        assert_eq!(err_json["status"], "error");
        assert_eq!(err_json["content"], "boom");
    }

    #[test]
    fn 流式行解析覆盖双协议() {
        assert!(matches!(
            parse_stream_line("data: [DONE]"),
            StreamLine::Done
        ));
        assert!(matches!(
            parse_stream_line(": ping"),
            StreamLine::Ignore
        ));
        let openai = parse_stream_line(
            r#"data: {"choices":[{"delta":{"content":"你"}}]}"#,
        );
        assert!(matches!(openai, StreamLine::Content(c) if c == "你"));
        let ollama_done =
            parse_stream_line(r#"{"model":"qwen","done":true,"message":{"content":""}}"#);
        assert!(matches!(ollama_done, StreamLine::Done));
        let ollama = parse_stream_line(r#"{"message":{"role":"assistant","content":"好"}}"#);
        assert!(matches!(ollama, StreamLine::Content(c) if c == "好"));
    }
}
