//! template 数据访问层(对齐 Python module_template/dao/*.py)
//!
//! 约定: 一组自由函数, 首参固定 `&DatabaseConnection`;
//! 只做数据库读写, 不做权限校验与响应组装(在 services 层)。

pub mod template;
