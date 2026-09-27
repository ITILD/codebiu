//! common —— 公共包(对齐 Python 侧 src/common)
//!
//! 顶层子模块与 Python common 子包一一对应:
//! - config/  分层配置加载(对应 config/index.py)+ 动态配置(对应 config/dynamic/)
//! - runtime  进程内运行时装配(对应 runtime.py): 全局 AppState(数据库连接/动态配置服务)
//! - utils/   公共工具: 统一错误与请求提取器(对应 utils/fastapiEX/)、分页
//!            (对应 utils/db/schema/pagination.py)、安全(对应 utils/security/)、中间件、
//!            表级运维注册中心(对应 db_rel.create_all/drop_all)

pub mod config;
pub mod runtime;
pub mod utils;

// 实体层(sys_config 表模型, 目录与 Python do/ 对齐; do 是 Rust 保留字, 模块名用 do_)
#[path = "do/mod.rs"]
pub mod do_;

/// 统一错误类型别名
pub type AppResult<T> = Result<T, utils::error::AppError>;

/// 公共包表注册(sys_config, app 启动期与其余模块 register_tables 一并调用)
pub fn register_tables() {
    utils::tables::register("sys_config", |s| {
        s.create_table_from_entity(do_::entity::sys_config::Entity)
    });
}
