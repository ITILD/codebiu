//! 服务层(按业务域拆分: 模型配置 / LLM 调用 / OCR / 重排序 / 语音)

pub mod llm;
pub mod model_config;
pub mod ocr;
pub mod rerank;
pub mod voice;
