//! 统一 JSON 请求体 / 查询参数提取器(对齐 Python FastAPI 的 pydantic 校验错误格式)
//!
//! 前端契约(422): `{"detail": [{loc, msg, type}, ...]}`。
//! axum 默认 Json/Query 的 rejection 文案为英文自由文本, 与 pydantic 数组结构不符,
//! 故统一改用 AppJson/AppQuery: 捕获 rejection 后解析 serde 错误并转为 pydantic 风格。

use serde::de::DeserializeOwned;

use axum::extract::rejection::{JsonRejection, QueryRejection};
use axum::extract::{FromRequest, FromRequestParts, Query, Request};
use axum::http::request::Parts;
use axum::Json;

use crate::utils::error::{AppError, ValidationErrorItem};

/// JSON 请求体提取器(Json<T> 的 pydantic 风格替换品)
pub struct AppJson<T>(pub T);

impl<T, S> FromRequest<S> for AppJson<T>
where
    T: DeserializeOwned,
    S: Send + Sync,
{
    type Rejection = AppError;

    async fn from_request(req: Request, state: &S) -> Result<Self, Self::Rejection> {
        match Json::<T>::from_request(req, state).await {
            Ok(Json(value)) => Ok(Self(value)),
            Err(rejection) => Err(map_json_rejection(rejection)),
        }
    }
}

/// 查询参数提取器(Query<T> 的 pydantic 风格替换品)
pub struct AppQuery<T>(pub T);

impl<T, S> FromRequestParts<S> for AppQuery<T>
where
    T: DeserializeOwned,
    S: Send + Sync,
{
    type Rejection = AppError;

    async fn from_request_parts(parts: &mut Parts, state: &S) -> Result<Self, Self::Rejection> {
        match Query::<T>::from_request_parts(parts, state).await {
            Ok(Query(value)) => Ok(Self(value)),
            Err(rejection) => {
                // 宽松重试: serde_urlencoded 对 #[serde(flatten)] 结构无法将字符串
                // 转为数字/布尔(对齐 FastAPI 的 query 类型自动转换语义);
                // 将 pairs 解析为类型推断后的 JSON 再反序列化, 仍失败才报 422。
                if let Some(q) = parts.uri.query() {
                    if let Ok(value) = loose_query_deserialize::<T>(q) {
                        return Ok(Self(value));
                    }
                }
                Err(map_query_rejection(rejection))
            }
        }
    }
}

/// 宽松查询串反序列化: 先按类型推断(数字/布尔)尝试, 失败后再按纯字符串尝试
///
/// 两次尝试分别覆盖: flatten 结构的数字字段(page=1→i64)与
/// 值恰为纯数字的字符串字段(name=123→String); 重复 key 聚合为数组。
fn loose_query_deserialize<T: DeserializeOwned>(q: &str) -> Result<T, ()> {
    let pairs: Vec<(String, String)> =
        form_urlencoded::parse(q.as_bytes()).map(|(k, v)| (k.into_owned(), v.into_owned())).collect();
    // 尝试一: 值类型推断(数字/布尔/null), 覆盖 flatten 数字字段
    let coerced = build_query_json(&pairs, true);
    if let Ok(v) = serde_json::from_value::<T>(coerced) {
        return Ok(v);
    }
    // 尝试二: 值全部保持字符串, 覆盖纯数字字符串字段
    let raw = build_query_json(&pairs, false);
    serde_json::from_value::<T>(raw).map_err(|_| ())
}

/// 将 pairs 构建为 JSON 对象(coerce=true 时做数字/布尔/null 类型推断)
fn build_query_json(pairs: &[(String, String)], coerce: bool) -> serde_json::Value {
    use serde_json::map::Entry;
    let mut map = serde_json::Map::new();
    for (k, v) in pairs {
        let val = if coerce { coerce_query_value(v) } else { serde_json::Value::String(v.clone()) };
        match map.entry(k.clone()) {
            // 重复 key 聚合为数组(对齐 serde_urlencoded 的 seq 语义)
            Entry::Occupied(mut e) => match e.get_mut() {
                serde_json::Value::Array(arr) => arr.push(val),
                single => {
                    let prev = single.take();
                    *e.get_mut() = serde_json::Value::Array(vec![prev, val]);
                }
            },
            Entry::Vacant(e) => {
                e.insert(val);
            }
        }
    }
    serde_json::Value::Object(map)
}

/// 查询值类型推断(FastAPI 语义: "1"→int, "true"→bool, "null"→null, 其余字符串)
fn coerce_query_value(v: &str) -> serde_json::Value {
    if let Ok(i) = v.parse::<i64>() {
        serde_json::Value::from(i)
    } else if let Ok(f) = v.parse::<f64>() {
        serde_json::Value::from(f)
    } else if v == "true" {
        serde_json::Value::Bool(true)
    } else if v == "false" {
        serde_json::Value::Bool(false)
    } else if v == "null" {
        serde_json::Value::Null
    } else {
        serde_json::Value::String(v.to_string())
    }
}

/// JSON rejection → 422(解析 serde 错误细节)
fn map_json_rejection(rej: JsonRejection) -> AppError {
    match rej {
        JsonRejection::JsonDataError(e) => parse_serde_error(&e.body_text(), "body"),
        JsonRejection::JsonSyntaxError(_) => AppError::Validation(vec![ValidationErrorItem {
            loc: vec!["body".to_string()],
            msg: "JSON decode error".to_string(),
            error_type: "json_invalid".to_string(),
        }]),
        other => AppError::Validation(vec![ValidationErrorItem {
            loc: vec!["body".to_string()],
            msg: other.body_text(),
            error_type: "value_error".to_string(),
        }]),
    }
}

/// Query rejection → 422(解析 serde 错误细节, loc 前缀为 query)
fn map_query_rejection(rej: QueryRejection) -> AppError {
    match rej {
        QueryRejection::FailedToDeserializeQueryString(e) => {
            parse_serde_error(&e.body_text(), "query")
        }
        other => AppError::Validation(vec![ValidationErrorItem {
            loc: vec!["query".to_string()],
            msg: other.body_text(),
            error_type: "value_error".to_string(),
        }]),
    }
}

/// 解析 serde 反序列化错误为 pydantic 风格校验项
///
/// 常见消息形态:
/// - `missing field \`pid\` at line 1 column 29` → type=missing, msg=Field required
/// - `invalid type: string "x", expected u32 at ...` → type=value_error, msg=Input should be ...
/// - 其它 → 原文作为 msg(前端可兜底展示)
fn parse_serde_error(text: &str, scope: &str) -> AppError {
    let mut loc = vec![scope.to_string()];
    let (error_type, msg);

    if let Some(field) = extract_field(text, "missing field `") {
        // 必填字段缺失
        loc.push(field);
        error_type = "missing".to_string();
        msg = "Field required".to_string();
    } else if text.contains("unknown field `") {
        // 未知字段: pydantic 默认忽略 extra, 该场景仅防御性输出
        let field = extract_field(text, "unknown field `").unwrap_or_default();
        loc.push(field);
        error_type = "extra_forbidden".to_string();
        msg = "Extra inputs are not permitted".to_string();
    } else if let Some(expected) = parse_invalid_type(text) {
        // 字段类型错误(loc 无法从 serde 消息恢复, 停在 body/query 级)
        error_type = "value_error".to_string();
        msg = format!("Input should be a valid {expected}");
    } else {
        error_type = "value_error".to_string();
        msg = text.to_string();
    }

    AppError::Validation(vec![ValidationErrorItem { loc, msg, error_type }])
}

/// 从 serde 消息中提取指定模式的反引号字段名
fn extract_field(text: &str, prefix: &str) -> Option<String> {
    let start = text.find(prefix)? + prefix.len();
    let rest = &text[start..];
    let end = rest.find('`')?;
    Some(rest[..end].to_string())
}

/// 解析 "invalid type: ..., expected X" 中的期望类型并映射为 pydantic 文案词
fn parse_invalid_type(text: &str) -> Option<&'static str> {
    if !text.contains("invalid type") {
        return None;
    }
    let expected = text
        .split("expected ")
        .nth(1)
        .unwrap_or_default()
        .split([' ', ','])
        .next()
        .unwrap_or_default();
    Some(map_expected_type(expected))
}

/// serde 类型名 → pydantic 人话词(拼入 "Input should be a valid {}")
fn map_expected_type(expected: &str) -> &'static str {
    match expected {
        "u8" | "u16" | "u32" | "u64" | "u128" | "usize" | "i8" | "i16" | "i32" | "i64"
        | "i128" | "isize" => "integer",
        "f32" | "f64" => "number",
        "bool" => "boolean",
        "str" | "a string" => "string",
        "a sequence" => "array",
        "a map" | "struct" => "object",
        _ => "value",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn 缺失字段解析为pydantic格式() {
        let err = parse_serde_error(
            "Failed to deserialize the JSON body into the target type: missing field `pid` at line 1 column 29",
            "body",
        );
        match err {
            AppError::Validation(items) => {
                assert_eq!(items[0].error_type, "missing");
                assert_eq!(items[0].msg, "Field required");
                assert_eq!(items[0].loc, vec!["body", "pid"]);
            }
            _ => panic!("应为 Validation 错误"),
        }
    }

    #[test]
    fn 类型错误解析为可读文案() {
        let err =
            parse_serde_error("invalid type: string \"x\", expected u32 at line 1 column 10", "body");
        match err {
            AppError::Validation(items) => {
                assert_eq!(items[0].msg, "Input should be a valid integer");
            }
            _ => panic!("应为 Validation 错误"),
        }
    }

    #[test]
    fn 未知消息保留原文() {
        let err = parse_serde_error("some weird failure", "query");
        match err {
            AppError::Validation(items) => {
                assert_eq!(items[0].msg, "some weird failure");
                assert_eq!(items[0].loc, vec!["query"]);
            }
            _ => panic!("应为 Validation 错误"),
        }
    }
}
