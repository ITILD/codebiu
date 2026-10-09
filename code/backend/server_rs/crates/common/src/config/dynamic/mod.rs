//! 动态配置中心(对齐 Python common/config/dynamic 包, 子模块一一对应)
//!
//! - schemas.rs  组元数据 + 9 组强类型结构体 + GROUPS 注册表(单一事实来源;
//!               对应 Python schemas.py 的 pydantic Settings 声明)
//! - dao.rs      sys_config 表行读写(对应 dao.py 的 SysConfigDao)
//! - service.rs  SettingsService: 类型化读取/校验写入/TTL 缓存/describe/首启种子
//!               (对应 service.py)
//!
//! 业务语义:
//! - 9 组配置(token/email/websearch/file_system/db_cache/db_vector/db_graph/tasks/admin)
//! - sys_config 表持久化, TTL 10s 缓存, 更新即时生效
//! - update: schema 感知深合并(未知字段 400 / secret 缺省保持 / 空串清除)
//! - describe: 字段元数据 + secret 打码, 直接驱动前端"通用配置"表单
//!
//! Rust 实现说明: 字段元数据用静态表声明(替代 Python 的 pydantic 反射),
//! 强类型校验通过各组 serde 结构体完成, 两类声明均集中在 schemas.rs。

pub mod dao;
pub mod schemas;
pub mod service;

// 对外出口(与拆分前 common::config::dynamic::X 路径兼容, 各模块无需改动)
pub use schemas::{
    schema_of, AdminSettings, DBCacheSettings, DBGraphSettings, DBVectorSettings, EmailSettings,
    FieldDef, FieldType, FileSystemSettings, GroupSchema, TasksSettings, TokenSettings,
    WebSearchSettings, GROUPS,
};
pub use service::SettingsService;
