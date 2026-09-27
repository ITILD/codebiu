//! module-site 数据访问层(对齐 Python module_site/dao/*.py)
//!
//! 约定: 每个 dao 模块一组自由函数, 首参固定 `&DatabaseConnection`;
//! 只做数据库读写, 不做权限校验与业务规则(可见性判定/统计组装在 services 层)。

pub mod blog;
pub mod ledger;
pub mod todolist;
