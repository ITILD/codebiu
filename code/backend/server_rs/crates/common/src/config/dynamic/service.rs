//! 动态配置服务(对齐 Python config/dynamic/service.py)
//!
//! - get_raw/get: 读取并缓存(默认 10s TTL; web 进程更新后本地缓存即时失效,
//!   其他进程(worker)最迟 TTL 后可见——简单可靠, 多副本部署再升级 Redis pub/sub)
//! - update: schema 感知深合并(未知字段 400 / secret 缺省保持 / 空串清除) + 校验落库
//! - describe: 组元数据 + 打码值(驱动前端通用表单, 后端加组前端零改动)
//! - seed_from_yaml: 首启种子(幂等, 不覆盖已有行)

use serde::de::DeserializeOwned;
use serde_json::Value;
use sea_orm::DatabaseConnection;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::Instant;

use super::dao;
use super::schemas::{schema_of, FieldType, GROUPS};
use crate::utils::error::AppError;
use crate::AppResult;

/// 点路径取值(如 "tavily.api_key" 在嵌套 JSON 中定位)
fn get_at<'a>(value: &'a Value, path: &str) -> Option<&'a Value> {
    let mut cursor = value;
    for seg in path.split('.') {
        cursor = cursor.get(seg)?;
    }
    Some(cursor)
}

/// 点路径写值(逐级创建缺失的对象节点)
fn set_at(value: &mut Value, path: &str, new_val: Value) {
    let mut cursor = value;
    let segs: Vec<&str> = path.split('.').collect();
    for seg in &segs[..segs.len() - 1] {
        if !cursor.is_object() {
            *cursor = serde_json::json!({});
        }
        cursor = cursor
            .as_object_mut()
            .expect("已确保为对象")
            .entry(seg.to_string())
            .or_insert(serde_json::json!({}));
    }
    if !cursor.is_object() {
        *cursor = serde_json::json!({});
    }
    cursor
        .as_object_mut()
        .expect("已确保为对象")
        .insert(segs[segs.len() - 1].to_string(), new_val);
}

/// patch 嵌套 JSON 拍平为点路径映射(list/标量整体保留)
fn flatten(value: &Value, prefix: &str, out: &mut HashMap<String, Value>) {
    match value {
        Value::Object(map) => {
            for (k, v) in map {
                let path = if prefix.is_empty() { k.clone() } else { format!("{prefix}.{k}") };
                flatten(v, &path, out);
            }
        }
        other => {
            // 前缀为空说明顶层是标量(非法 patch), 仍记录以便报未知字段
            if prefix.is_empty() {
                out.insert("__root__".to_string(), other.clone());
            } else {
                out.insert(prefix.to_string(), other.clone());
            }
        }
    }
}

/// 动态配置服务(进程级单例, 持数据库连接)
pub struct SettingsService {
    db: DatabaseConnection,
    /// TTL 缓存: 组名 -> (写入时刻, 当前值)
    cache: Mutex<HashMap<String, (Instant, Value)>>,
}

impl SettingsService {
    /// TTL 10s(其他进程如 worker 的陈旧窗口)
    const TTL: std::time::Duration = std::time::Duration::from_secs(10);

    pub fn new(db: DatabaseConnection) -> Arc<Self> {
        Arc::new(Self { db, cache: Mutex::new(HashMap::new()) })
    }

    /// 按组读取当前值(默认值 + 库行深合并, TTL 缓存)
    pub async fn get_raw(&self, group: &str) -> AppResult<Value> {
        let schema = schema_of(group)?;
        if let Some((at, value)) = self.cache.lock().expect("缓存锁").get(group) {
            if at.elapsed() <= Self::TTL {
                return Ok(value.clone());
            }
        }
        let row = dao::find_row(&self.db, group).await?;
        let row_value = row.and_then(|r| r.value).unwrap_or_else(|| serde_json::json!({}));
        let mut merged = (schema.defaults)();
        crate::config::deep_merge(&mut merged, &row_value);
        // 规范化(类型纠正/默认兜底)
        let value = (schema.validate)(&merged).map_err(AppError::business)?;
        self.cache
            .lock()
            .expect("缓存锁")
            .insert(group.to_string(), (Instant::now(), value.clone()));
        Ok(value)
    }

    /// 类型化读取(反序列化到强类型结构体)
    pub async fn get<T: DeserializeOwned>(&self, group: &str) -> AppResult<T> {
        let raw = self.get_raw(group).await?;
        serde_json::from_value(raw)
            .map_err(|e| AppError::Internal(format!("配置反序列化失败: {e}")))
    }

    /// 更新配置组: 未知字段 400 / secret 缺省保持 / 空串清除 / 校验落库 / 缓存失效
    pub async fn update(&self, group: &str, patch: &Value, updated_by: &str) -> AppResult<()> {
        let schema = schema_of(group)?;
        if !patch.is_object() {
            return Err(AppError::business("配置更新数据必须是对象"));
        }
        let mut patch_flat = HashMap::new();
        flatten(patch, "", &mut patch_flat);
        schema.check_unknown(&patch_flat).map_err(AppError::business)?;

        let mut merged = self.get_raw(group).await?;
        for (path, value) in patch_flat {
            // secret 字段: null/空串=清除, 有值=覆盖
            let new_val = if schema.secrets.contains(&path.as_str())
                && (value.is_null() || matches!(&value, Value::String(s) if s.is_empty()))
            {
                Value::String(String::new())
            } else {
                value
            };
            set_at(&mut merged, &path, new_val);
        }
        // 强类型校验 + 规范化(校验失败 → 400)
        let normalized = (schema.validate)(&merged).map_err(AppError::business)?;

        dao::upsert_row(&self.db, group, &normalized, Some(updated_by)).await?;
        // 写入即刷新缓存(即时生效)
        self.cache
            .lock()
            .expect("缓存锁")
            .insert(group.to_string(), (Instant::now(), normalized));
        Ok(())
    }

    /// 单组描述(元数据 + 打码值, 驱动前端表单)
    pub async fn describe(&self, group: &str) -> AppResult<Value> {
        let schema = schema_of(group)?;
        let row = dao::find_row(&self.db, group).await?;
        let dump = self.get_raw(group).await?;
        let fields: Vec<Value> = schema
            .fields
            .iter()
            .map(|fdef| {
                let mut meta = serde_json::json!({
                    "key": fdef.key,
                    "title": fdef.title,
                    "description": fdef.description,
                    "type": fdef.ftype.as_str(),
                    "options": if fdef.options.is_empty() { Value::Null } else { serde_json::json!(fdef.options) },
                    "required": fdef.required,
                });
                let obj = meta.as_object_mut().expect("json 对象");
                if fdef.ftype == FieldType::Secret {
                    let has = get_at(&dump, fdef.key)
                        .map(|v| matches!(v, Value::String(s) if !s.is_empty()))
                        .unwrap_or(false);
                    obj.insert("value".into(), Value::Null);
                    obj.insert("has_value".into(), serde_json::json!(has));
                } else {
                    let value = get_at(&dump, fdef.key).cloned().unwrap_or(Value::Null);
                    obj.insert("value".into(), value);
                }
                meta
            })
            .collect();
        Ok(serde_json::json!({
            "group": schema.group,
            "name": schema.name,
            "description": schema.description,
            "restart_required": schema.restart_required,
            "updated_at": row.as_ref().map(|r| r.updated_at.to_rfc3339()),
            "updated_by": row.as_ref().and_then(|r| r.updated_by.clone()),
            "fields": fields,
        }))
    }

    /// 全部组描述
    pub async fn describe_all(&self) -> AppResult<Vec<Value>> {
        let mut result = Vec::with_capacity(GROUPS.len());
        for schema in GROUPS {
            result.push(self.describe(schema.group).await?);
        }
        Ok(result)
    }

    /// 首启种子: 组行不存在时, 以 yaml 同名节覆盖默认值建行(幂等, 不覆盖已有行)
    pub async fn seed_from_yaml(&self, raw_config: &Value) -> AppResult<()> {
        for schema in GROUPS {
            if dao::find_row(&self.db, schema.group).await?.is_some() {
                continue;
            }
            let section = raw_config.get(schema.group).cloned().unwrap_or(Value::Null);
            let mut merged = (schema.defaults)();
            crate::config::deep_merge(&mut merged, &section);
            let value = (schema.validate)(&merged).map_err(AppError::business)?;
            dao::upsert_row(&self.db, schema.group, &value, Some("seed")).await?;
            tracing::info!("动态配置组 '{}' 已按 yaml 种子初始化", schema.group);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn 拍平与点路径读写() {
        let patch = serde_json::json!({"tavily": {"api_key": "k"}, "max_results": 5});
        let mut flat = HashMap::new();
        flatten(&patch, "", &mut flat);
        assert_eq!(flat.len(), 2);
        assert!(flat.contains_key("tavily.api_key"));
        assert!(flat.contains_key("max_results"));

        let mut v = serde_json::json!({"tavily": {"api_key": ""}});
        set_at(&mut v, "tavily.api_key", serde_json::json!("x"));
        assert_eq!(v["tavily"]["api_key"], "x");
        set_at(&mut v, "firecrawl.api_base", serde_json::json!("http://a"));
        assert_eq!(v["firecrawl"]["api_base"], "http://a");
    }
}
