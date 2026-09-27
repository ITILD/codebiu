//! module-authorization 请求/响应类型(对齐 Python module_authorization/do/*.py)
//!
//! 注: 日期时间序列化为 RFC3339; Option 字段序列化为 null(与 pydantic 行为一致)

// 表模型层(sea-orm 实体, 对齐 Python do/*.py 的表模型部分)
pub mod entity;

pub mod auth;
pub mod casbin_rule;
pub mod dept;
pub mod permission;
pub mod role;
pub mod token;
pub mod user;

use chrono::{DateTime, FixedOffset, Utc};

/// 当前时间(带时区偏移, 与 Python datetime.now(timezone.utc) 等价)
pub fn now_utc() -> DateTime<FixedOffset> {
    Utc::now().fixed_offset()
}

/// parent_id 字段的 serde 默认值("0" 表示根节点, 与 Python 模型默认值一致)
pub fn default_parent_id() -> String {
    "0".to_string()
}
