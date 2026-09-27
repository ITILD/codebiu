//! module-site 业务逻辑层(对齐 Python module_site/service/*.py)
//!
//! 业务规则(可见性判定/分页组装/统计聚合)在此层; 数据读写委托 dao 层。

pub mod blog;
pub mod ledger;
pub mod todolist;
