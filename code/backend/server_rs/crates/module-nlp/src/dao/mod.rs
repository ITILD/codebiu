//! nlp 数据访问层(对齐 Python module_nlp/dao/*.py)
//!
//! 约定: 一组自由函数, 首参固定 `&DatabaseConnection`;
//! 只做数据库读写, 不做归属校验/差集计算/聚合组装(在 services 层)。

pub mod synonym;
