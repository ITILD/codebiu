//! 数据库元信息数据对象(对齐 Python module_main/do/db.py)

use serde::Serialize;

/// 关系库数据表元信息(对齐 /db/tables 返回项)
#[derive(Debug, Clone, Serialize)]
pub struct TableMeta {
    pub name: String,
    pub comment: Option<String>,
    pub column_count: i64,
    pub row_count: i64,
    /// 最近更新时间(MAX(updated_at), ISO 字符串)
    pub last_updated: Option<String>,
}
