//! nlp 模块请求/响应类型(对齐 Python module_nlp/do/*.py 的非表模型)
//!
//! 表模型在 entity/ 子目录(sea-orm 实体); 此处只放 Create/Update/Response DTO 与校验逻辑。
//! Update 类型: 非空字段 `Option<T>`, 可空字段 `Option<Option<T>>` 三态:
//! 未传(字段缺失) → 不更新; 传 null → 置 NULL; 传值 → 更新。

// 表模型层(sea-orm 实体)
pub mod entity;

pub mod synonym;

use chrono::{DateTime, FixedOffset, Utc};

/// 当前时间(带时区偏移, 与 Python datetime.now(timezone.utc) 等价)
pub fn now_utc() -> DateTime<FixedOffset> {
    Utc::now().fixed_offset()
}
