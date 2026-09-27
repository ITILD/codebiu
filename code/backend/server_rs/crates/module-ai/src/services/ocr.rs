//! OCR 服务门面(对齐 Python module_ai/service/ocr.py)
//!
//! 降级约定: 本地 ONNX OCR 流水线(Paddle 检测/分类/识别)与版面分析模型未在 Rust
//! 服务实现; 在线方案(DashScope qwen-vl-ocr)由模型配置表驱动(model_type=ocr,
//! server_type=dashscope), 以 reqwest 实现。
//! 分栏分段纯算法引擎(MultiPara)未实现, segment_layout 结果与 recognize 一致。

use sea_orm::DatabaseConnection;
use serde_json::{json, Value};

use common::utils::error::AppError;

use crate::dao::model_config as dao;
use crate::utils::ocr::DashscopeOcr;

/// 本地 OCR 引擎未实现的统一提示文案
pub const LOCAL_ENGINE_UNAVAILABLE: &str =
    "本地 OCR 引擎未实现，请使用 online 引擎或部署 Python 服务";

/// 读取 OCR 配置中支持的语言列表(返回 [{code, name}], 供前端选择识别语言; 缺配置返回空数组)
pub fn get_ocr_languages() -> Value {
    let Some(languages) = common::config::raw_json()
        .get("ocr")
        .and_then(|o| o.get("languages"))
        .and_then(Value::as_object)
    else {
        return Value::Array(vec![]);
    };
    Value::Array(
        languages
            .iter()
            .map(|(code, val)| {
                json!({
                    "code": code,
                    "name": val.get("name").cloned().unwrap_or(Value::String(code.clone())),
                })
            })
            .collect(),
    )
}

/// 获取 DashScope OCR 引擎(模型配置表 model_type=ocr 且 server_type=dashscope 的最优先记录)
async fn get_ocr_engine(
    db: &DatabaseConnection,
) -> Result<Option<crate::do_::entity::model_config::Model>, AppError> {
    dao::get_first_by_type(db, "ocr", Some("dashscope")).await
}

/// 组装 DashScope OCR 引擎(无可用 online 配置时按本地引擎未实现降级提示)
async fn build_online_engine(db: &DatabaseConnection) -> Result<DashscopeOcr, AppError> {
    let Some(config) = get_ocr_engine(db).await? else {
        return Err(AppError::business(LOCAL_ENGINE_UNAVAILABLE));
    };
    // model/url/api_key 来自配置列, prompt/timeout 来自 extra 扩展字段
    let conf = json!({
        "model": config.model,
        "url": config.url,
        "api_key": config.api_key,
        "prompt": config.extra.as_ref().and_then(|e| e.get("prompt")).and_then(Value::as_str),
        "timeout": config.extra.as_ref().and_then(|e| e.get("timeout")).and_then(Value::as_u64),
    });
    DashscopeOcr::from_conf(&conf)
}

/// 执行文字识别(启用检测与分类; 返回含文本框坐标/置信度/耗时)
pub async fn recognize(
    db: &DatabaseConnection,
    http: &reqwest::Client,
    image: &[u8],
    _lang: &str,
) -> Result<Value, AppError> {
    let engine = build_online_engine(db).await?;
    engine.recognize(http, image).await
}

/// 执行文字识别/分栏分段(分段引擎未实现, 结果与 recognize 一致)
pub async fn segment_layout(
    db: &DatabaseConnection,
    http: &reqwest::Client,
    image: &[u8],
    lang: &str,
) -> Result<Value, AppError> {
    recognize(db, http, image, lang).await
}

/// 版面分析(识别标题/图片/表格/目录区域; 本地版面分析模型未在 Rust 服务实现)
pub async fn layout() -> Result<Value, AppError> {
    Err(AppError::business(LOCAL_ENGINE_UNAVAILABLE))
}

/// 组合接口: 文字识别 + 分栏分段 + 版面分析(版面区域未实现置空数组)
pub async fn recognize_all(
    db: &DatabaseConnection,
    http: &reqwest::Client,
    image: &[u8],
    lang: &str,
    _inpaint: bool,
) -> Result<Value, AppError> {
    let mut result = segment_layout(db, http, image, lang).await?;
    if let Some(obj) = result.as_object_mut() {
        obj.insert("layout".to_string(), Value::Array(vec![]));
    }
    Ok(result)
}
