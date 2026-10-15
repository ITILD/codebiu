//! langchain-rust LLM trait 适配器(对齐 Python 经 LangChain 构建模型实例的接口层地位)
//!
//! 以适配器模式包裹自有 `LlmTarget` HTTP 客户端(而非 langchain-rust 内置的
//! OpenAI/Ollama client), 从而:
//! - 保留项目定制: enable_thinking / reasoning_content 解析 / "始终思考"模型回退、
//!   openai 兼容与 ollama 双协议、配置化超时与鉴权;
//! - 获得 langchain 生态兼容: 适配器可直接用作 `Box<dyn LLM>` 传入 chain/agent。
//!
//! 流式增量映射(langchain `StreamData`):
//! - 正文增量 → `content` 携带增量文本, `value` 为 `{"content": ...}`;
//! - 思考增量 → `content` 为空, `value` 为 `{"reasoning_content": ...}`
//!   (调用方可从 value 读取思考流, 对应 AG-UI REASONING_* 事件)。

use std::pin::Pin;

use async_trait::async_trait;
use futures::Stream;
use langchain_rust::language_models::llm::LLM;
use langchain_rust::language_models::{GenerateResult, LLMError};
use langchain_rust::schemas::{Message as LcMessage, StreamData};
use serde_json::{json, Value};
use tokio_stream::wrappers::ReceiverStream as TokioReceiverStream;
use tokio_stream::StreamExt;

use super::llm::{self, LlmTarget};
use crate::do_::llm::Message;

/// LLM 调用适配器: `LlmTarget` + HTTP 客户端 → langchain-rust `LLM` trait
#[derive(Clone)]
pub struct LangchainChatModel {
    target: LlmTarget,
    http: reqwest::Client,
}

impl LangchainChatModel {
    /// 从调用目标与 HTTP 客户端构建(app.http 或独立客户端均可)
    ///
    /// 注: `stream` 内部走 llm::chat_stream 的流式专用客户端(无总超时),
    /// 此处 http 客户端仅服务非流式 `generate`。
    pub fn new(target: LlmTarget, http: reqwest::Client) -> Self {
        Self { target, http }
    }
}

/// langchain 消息 → 自有 REST 消息(role 用 langchain 别名, 由 wire_role 归一化;
/// tool 角色无自有协议对应, 落 system 分支)
fn to_wire_message(m: &LcMessage) -> Message {
    Message {
        role: m.message_type.to_string(),
        content: m.content.clone(),
        additional_kwargs: Value::Null,
    }
}

/// chat 响应 content(字符串或分段数组) → 纯文本
fn value_to_text(v: &Value) -> String {
    match v {
        Value::String(s) => s.clone(),
        // openai 分段 content: [{"type":"text","text":"..."}, ...]
        Value::Array(parts) => parts
            .iter()
            .filter_map(|p| p.get("text").and_then(Value::as_str))
            .collect(),
        _ => String::new(),
    }
}

#[async_trait]
impl LLM for LangchainChatModel {
    async fn generate(&self, messages: &[LcMessage]) -> Result<GenerateResult, LLMError> {
        let msgs: Vec<Message> = messages.iter().map(to_wire_message).collect();
        let content = llm::chat_once(&self.http, &self.target, &msgs)
            .await
            .map_err(|e| LLMError::OtherError(e.to_string()))?;
        Ok(GenerateResult {
            tokens: None,
            generation: value_to_text(&content),
        })
    }

    async fn stream(
        &self,
        messages: &[LcMessage],
    ) -> Result<Pin<Box<dyn Stream<Item = Result<StreamData, LLMError>> + Send>>, LLMError>
    {
        let msgs: Vec<Message> = messages.iter().map(to_wire_message).collect();
        let rx = llm::chat_stream(self.target.clone(), &msgs)
            .map_err(|e| LLMError::OtherError(e.to_string()))?;
        let stream = TokioReceiverStream::new(rx).map(|item| {
            item.map(|delta| match delta {
                llm::StreamDelta::Content(text) => {
                    StreamData::new(json!({"content": text}), None, text)
                }
                llm::StreamDelta::Reasoning(text) => StreamData::new(
                    json!({"reasoning_content": text}),
                    None,
                    String::new(),
                ),
            })
            .map_err(|e| LLMError::OtherError(e.to_string()))
        });
        Ok(Box::pin(stream))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use langchain_rust::schemas::MessageType;

    #[test]
    fn langchain消息角色映射() {
        let human = to_wire_message(&LcMessage::new_human_message("你好"));
        assert_eq!(human.role, "human");
        assert_eq!(human.content, "你好");
        let ai = to_wire_message(&LcMessage::new_ai_message("在"));
        assert_eq!(ai.role, "ai");
        let system = to_wire_message(&LcMessage::new_system_message("规则"));
        assert_eq!(system.role, "system");
        let tool = to_wire_message(&LcMessage::new_tool_message("结果", "call_1"));
        assert_eq!(tool.role, "tool");
    }

    #[test]
    fn 响应content转纯文本() {
        assert_eq!(value_to_text(&json!("直接回答")), "直接回答");
        let parts = json!([{"type": "text", "text": "段1"}, {"type": "text", "text": "段2"}]);
        assert_eq!(value_to_text(&parts), "段1段2");
        assert_eq!(value_to_text(&Value::Null), "");
    }

    /// 适配器满足 trait object 用法(Box<dyn LLM> 由 From 自动转换)
    #[test]
    fn 适配器可作trait对象() {
        let model = LangchainChatModel::new(
            LlmTarget {
                model_type: "chat".into(),
                server_type: "openai".into(),
                model: "gpt".into(),
                url: "http://localhost:1".into(),
                api_key: None,
                temperature: 0.7,
                timeout: 1,
                no_think: false,
                out_tokens: 8,
            },
            reqwest::Client::new(),
        );
        let _boxed: Box<dyn LLM> = model.clone().into();
        assert_eq!(model.target.model, "gpt");
    }

    #[test]
    fn 思考增量映射为reasoning_value() {
        // 构造逻辑验证: StreamData 携带 reasoning_content 且 content 为空
        let delta = llm::StreamDelta::Reasoning("推理".into());
        let data = match delta {
            llm::StreamDelta::Content(text) => {
                StreamData::new(json!({"content": text.clone()}), None, text)
            }
            llm::StreamDelta::Reasoning(text) => {
                StreamData::new(json!({"reasoning_content": text}), None, String::new())
            }
        };
        assert_eq!(data.content, "");
        assert_eq!(data.value["reasoning_content"], "推理");
        let _ = MessageType::ToolMessage; // role 类型覆盖引用
    }
}
