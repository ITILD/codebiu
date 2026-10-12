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

/// 向量库表清单(表名/字段数/向量维度/数据条数; 未启用时与 Python 一致返回空)
pub async fn vector_tables(state: &common::runtime::AppState) -> serde_json::Value {
    use serde_json::json;
    let Some(client) = common::utils::db_vector::get(state).await else {
        return json!({ "type": serde_json::Value::Null, "tables": [] });
    };
    let type_name = state
        .settings
        .get::<common::config::dynamic::schemas::DBVectorSettings>("db_vector")
        .await
        .map(|c| c.r#type)
        .unwrap_or_default();
    let names = client.list_collections().await.unwrap_or_default();
    let mut tables = Vec::with_capacity(names.len());
    for name in names {
        let describe = client.describe_collection(&name).await.ok();
        // 字段数与向量维度取自 describe(失败时降级 0/None)
        let (field_count, vector_dims) = describe
            .as_ref()
            .and_then(|d| d.get("fields").and_then(|f| f.as_array()))
            .map(|fields| {
                let dims: Option<i64> = fields
                    .iter()
                    .find(|f| f.get("type").and_then(|t| t.as_str()) == Some("FloatVector"))
                    .and_then(|f| {
                        f.get("params").and_then(|p| p.as_array()).and_then(|ps| {
                            ps.iter()
                                .find(|p| p.get("key").and_then(|k| k.as_str()) == Some("dim"))
                                .and_then(|p| p.get("value"))
                                .and_then(|v| v.as_str())
                                .and_then(|v| v.parse().ok())
                        })
                    });
                (fields.len(), dims)
            })
            .unwrap_or((0, None));
        let row_count = client.collection_count(&name).await.unwrap_or(0);
        tables.push(json!({
            "name": name,
            "field_count": field_count,
            "vector_dims": vector_dims,
            "row_count": row_count,
        }));
    }
    json!({ "type": type_name, "tables": tables })
}

/// 缓存数据库信息(P1 未接入 Redis: 与 Python 未启用时一致)
pub async fn cache_info() -> serde_json::Value {
    serde_json::json!({ "type": serde_json::Value::Null })
}

/// 图数据库信息(P1 未接入图数据库: 与 Python 未启用时一致)
pub async fn graph_info() -> serde_json::Value {
    serde_json::json!({ "type": serde_json::Value::Null })
}
