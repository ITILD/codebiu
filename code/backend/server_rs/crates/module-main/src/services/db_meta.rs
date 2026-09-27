//! 数据库元信息只读服务(对齐 Python service/db_meta.py)
//!
//! 统一统计关系库/向量库/缓存/图数据库的运行信息, 供数据监测页消费。
//! P1 阶段仅关系库真实实现; 向量/缓存/图库未接入时返回 {"type": null}(与 Python 未启用一致)。

use sea_orm::DatabaseConnection;

use common::utils::error::AppError;

use crate::dao;
use crate::do_::db::TableMeta;

/// 创建所有未创建的数据库表
pub async fn create_all(db: &DatabaseConnection) -> Result<(), AppError> {
    dao::db_meta::create_all(db).await
}

/// 删除所有数据库表(重置流程先删后建)
pub async fn drop_all(db: &DatabaseConnection) -> Result<(), AppError> {
    dao::db_meta::drop_all(db).await
}

/// 列出关系库全部数据表及数据量/最近更新时间(表名/注释关键字过滤)
pub async fn tables(
    db: &DatabaseConnection,
    keyword: Option<&str>,
) -> Result<Vec<TableMeta>, AppError> {
    dao::db_meta::tables(db, keyword).await
}

/// 向量库表清单(P1 未接入向量库: 与 Python 未启用时一致)
pub async fn vector_tables() -> serde_json::Value {
    serde_json::json!({ "type": serde_json::Value::Null, "tables": [] })
}

/// 缓存数据库信息(P1 未接入 Redis: 与 Python 未启用时一致)
pub async fn cache_info() -> serde_json::Value {
    serde_json::json!({ "type": serde_json::Value::Null })
}

/// 图数据库信息(P1 未接入图数据库: 与 Python 未启用时一致)
pub async fn graph_info() -> serde_json::Value {
    serde_json::json!({ "type": serde_json::Value::Null })
}
