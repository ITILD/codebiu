//! 授权模块控制器(对齐 Python controller/*.py)
//!
//! 薄层约定: 只做请求提取 + 权限校验 + 调用 services + HTTP 包装;
//! 业务规则在 services 层, 数据库读写 dao 层。

pub mod auth;
pub mod casbin_rule;
pub mod dept;
pub mod permission;
pub mod role;
pub mod token;
pub mod user;
