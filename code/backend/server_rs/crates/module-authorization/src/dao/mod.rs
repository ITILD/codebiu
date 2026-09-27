//! module-authorization 数据访问层(对齐 Python module_authorization/dao/*.py)
//!
//! 约定: 每个 dao 模块一组自由函数, 首参固定 `&DatabaseConnection`;
//! 只做数据库读写, 不做权限校验与业务规则(重名校验/密码哈希/树形组装在 services 层)。
//! 历史语义保留: 部分查询辅助函数按原实现吞掉数据库异常返回 Option(调用方自行判定缺失语义)。

pub mod dept;
pub mod permission;
pub mod role;
pub mod token;
pub mod user;
