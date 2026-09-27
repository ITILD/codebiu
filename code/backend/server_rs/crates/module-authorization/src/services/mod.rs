//! 授权模块服务层(对齐 Python service/*.py)
//!
//! - user: 用户业务(重名校验/密码哈希/认证)
//! - role / permission / dept: 运行期 CRUD 业务(数据库读写委托 dao 层)
//! - token: 令牌签发/验证/撤销
//! - role_table / perm_table: 声明表幂等同步(casbin 启动引导用)

pub mod dept;
pub mod perm_table;
pub mod permission;
pub mod role;
pub mod role_table;
pub mod token;
pub mod user;
