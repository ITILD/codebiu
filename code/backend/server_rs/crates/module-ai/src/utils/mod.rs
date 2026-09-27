//! 工具层(对齐 Python module_ai/utils)
//!
//! - llm: LLM REST 调用/SSE 事件组装(等价 utils/llm/factory + utils/llm/stream)
//! - ocr: DashScope 在线 OCR 引擎(等价 utils/ocr/dashscope.py)
//! - rerank: 重排序引擎三协议实现(等价 utils/llm/rerank)

pub mod llm;
pub mod ocr;
pub mod rerank;

/// 截断响应体文本到 500 字符(对齐 Python `body[:500]` 的错误日志/报文习惯)
pub(crate) fn truncate_body(body: &str) -> String {
    body.chars().take(500).collect()
}
