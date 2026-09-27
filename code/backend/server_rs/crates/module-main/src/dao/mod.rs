//! module-main 数据访问层(对齐 Python module_main/dao/*.py)
//!
//! 约定: 每个 dao 模块一组自由函数, 首参固定 `&DatabaseConnection`;
//! 只做数据库读写, 不做分页组装与业务组装(在 services 层)。

pub mod db_meta;
pub mod dict_item;
pub mod dict_type;
