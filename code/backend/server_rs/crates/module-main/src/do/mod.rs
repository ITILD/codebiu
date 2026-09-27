//! module-main 请求/响应类型(对齐 Python module_main/do/*.py 的非表模型)
//!
//! Update 模型语义与 pydantic exclude_unset 一致:
//! - 必填字段(type_code 等)缺失 → 422
//! - 可选标量字段用 Option<T>: 未传 → 不更新, 传 null → 422(与 pydantic 类型不符一致)
//! - 可空字符串字段用 Option<Option<T>>: 未传 → 不更新, 传 null → 更新为 NULL

// 表模型层(sea-orm 实体, 对齐 Python do/*.py 的表模型部分)
pub mod entity;

pub mod db;
pub mod dict_item;
pub mod dict_type;
pub mod status;
pub mod sys_config;

/// serde 缺省值: true(布尔字段缺省为激活态, 对齐 pydantic 默认 True)
pub fn d_true() -> bool {
    true
}
