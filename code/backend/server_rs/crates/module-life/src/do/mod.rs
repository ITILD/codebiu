//! module-life 请求/响应类型(对齐 Python module_life/do/*.py 的非表模型)
//!
//! 表模型在 entity/ 子目录(sea-orm 实体); 此处只放 Create/Update/Response DTO 与枚举。
//! Update 类型可空字段使用 `Option<Option<T>>` 三态:
//! 未传(字段缺失) → 不更新; 传 null → 置 NULL; 传值 → 更新。
//! 枚举请求值与 Python API 一致(小写 boy/traditional...); 数据库存量为代码生成的
//! 大写值(BOY/TRADITIONAL...), 在 baby_name 模块完成双向映射, 保证前端契约零改动。

// 表模型层(sea-orm 实体)
pub mod entity;

pub mod almanac;
pub mod baby_name;
pub mod predict;

use chrono::{DateTime, FixedOffset, Utc};

/// 当前时间(带时区偏移, 与 Python datetime.now(timezone.utc) 等价)
pub fn now_utc() -> DateTime<FixedOffset> {
    Utc::now().fixed_offset()
}
