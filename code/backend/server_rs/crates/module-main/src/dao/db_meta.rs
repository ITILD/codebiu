//! 数据库元信息数据访问(对齐 Python module_main/dao/db_meta.py + 表管理)
//!
//! 统计关系库的表清单/数据量/最近更新时间; 并提供全表建/删(供 /db/create 与 /db/reset)。

use sea_orm::{ConnectionTrait, DatabaseConnection, DbBackend, Statement};

use common::utils::error::AppError;

use crate::do_::db::TableMeta;

/// 创建所有未创建的数据库表
pub async fn create_all(db: &DatabaseConnection) -> Result<(), AppError> {
    common::utils::tables::create_all(db).await?;
    Ok(())
}

/// 删除所有数据库表(重置流程先删后建)
pub async fn drop_all(db: &DatabaseConnection) -> Result<(), AppError> {
    common::utils::tables::drop_all(db).await?;
    Ok(())
}

/// 列出关系库全部数据表及数据量/最近更新时间(表名/注释关键字过滤, 不区分大小写)
pub async fn tables(
    db: &DatabaseConnection,
    keyword: Option<&str>,
) -> Result<Vec<TableMeta>, AppError> {
    let backend = db.get_database_backend();
    // 表清单: postgres 查 pg_class(含注释), sqlite 查 sqlite_master(无表注释)
    let mut tables: Vec<(String, Option<String>)> = match backend {
        DbBackend::Postgres => {
            let rows = db
                .query_all(Statement::from_string(
                    backend,
                    "SELECT c.relname AS name, obj_description(c.oid, 'pg_class') AS comment \
                     FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace \
                     WHERE n.nspname = 'public' AND c.relkind = 'r' ORDER BY c.relname"
                        .to_string(),
                ))
                .await?;
            rows.into_iter()
                .map(|r| {
                    Ok((
                        r.try_get::<String>("", "name")?,
                        r.try_get::<Option<String>>("", "comment")?,
                    ))
                })
                .collect::<Result<Vec<_>, sea_orm::DbErr>>()?
        }
        _ => {
            let rows = db
                .query_all(Statement::from_string(
                    backend,
                    "SELECT name FROM sqlite_master WHERE type='table' \
                     AND name NOT LIKE 'sqlite_%' ORDER BY name"
                        .to_string(),
                ))
                .await?;
            rows.into_iter()
                .map(|r| Ok((r.try_get::<String>("", "name")?, None)))
                .collect::<Result<Vec<_>, sea_orm::DbErr>>()?
        }
    };

    // keyword 过滤(表名 + 注释拼接后小写匹配, 对齐 Python)
    if let Some(kw) = keyword.filter(|k| !k.is_empty()) {
        let kw = kw.to_lowercase();
        tables.retain(|(name, comment)| {
            format!("{name} {}", comment.clone().unwrap_or_default()).to_lowercase().contains(&kw)
        });
    }

    let mut metas = Vec::with_capacity(tables.len());
    for (name, comment) in tables {
        let quoted = format!("\"{}\"", name.replace('"', "\"\""));
        // 列数(information_schema / pragma_table_info)
        let column_count = match backend {
            DbBackend::Postgres => db
                .query_one(Statement::from_sql_and_values(
                    backend,
                    "SELECT COUNT(*) AS cnt FROM information_schema.columns \
                     WHERE table_schema = 'public' AND table_name = $1",
                    [name.clone().into()],
                ))
                .await?
                .and_then(|r| r.try_get::<i64>("", "cnt").ok())
                .unwrap_or(0),
            _ => db
                .query_one(Statement::from_string(
                    backend,
                    format!("SELECT COUNT(*) AS cnt FROM pragma_table_info(\"{name}\")"),
                ))
                .await?
                .and_then(|r| r.try_get::<i64>("", "cnt").ok())
                .unwrap_or(0),
        };
        // 数据条数(统计失败按 0 处理, 对齐 Python try/except pass)
        let row_count = db
            .query_one(Statement::from_string(
                backend,
                format!("SELECT COUNT(*) AS cnt FROM {quoted}"),
            ))
            .await
            .ok()
            .flatten()
            .and_then(|r| r.try_get::<i64>("", "cnt").ok())
            .unwrap_or(0);
        // 最近更新时间(声明 updated_at 字段时才统计, 取 MAX 为 ISO 字符串)
        let last_updated = last_updated_of(db, backend, &name, &quoted).await?;
        metas.push(TableMeta { name, comment, column_count, row_count, last_updated });
    }
    Ok(metas)
}

/// 单表 MAX(updated_at) 统计(无该列/统计失败 → None)
async fn last_updated_of(
    db: &DatabaseConnection,
    backend: DbBackend,
    name: &str,
    quoted: &str,
) -> Result<Option<String>, AppError> {
    // 列存在性检查
    let has_updated_at = match backend {
        DbBackend::Postgres => db
            .query_one(Statement::from_sql_and_values(
                backend,
                "SELECT COUNT(*) AS cnt FROM information_schema.columns \
                 WHERE table_schema = 'public' AND table_name = $1 AND column_name = 'updated_at'",
                [name.to_string().into()],
            ))
            .await?
            .and_then(|r| r.try_get::<i64>("", "cnt").ok())
            .unwrap_or(0)
            > 0,
        _ => db
            .query_one(Statement::from_string(
                backend,
                format!(
                    "SELECT COUNT(*) AS cnt FROM pragma_table_info(\"{name}\") WHERE name = 'updated_at'"
                ),
            ))
            .await?
            .and_then(|r| r.try_get::<i64>("", "cnt").ok())
            .unwrap_or(0)
            > 0,
    };
    if !has_updated_at {
        return Ok(None);
    }
    let sql = format!("SELECT MAX(updated_at) AS last_updated FROM {quoted}");
    let Some(row) = db.query_one(Statement::from_string(backend, sql)).await.ok().flatten() else {
        return Ok(None);
    };
    // postgres 返回 timestamptz → ISO 字符串; sqlite 返回 TEXT 原样
    let value = match backend {
        DbBackend::Postgres => row
            .try_get::<Option<chrono::DateTime<chrono::FixedOffset>>>("", "last_updated")
            .ok()
            .flatten()
            .map(|dt| dt.to_rfc3339()),
        _ => row.try_get::<Option<String>>("", "last_updated").ok().flatten(),
    };
    Ok(value)
}
