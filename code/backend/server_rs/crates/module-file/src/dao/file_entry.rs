//! 文件条目数据访问(对齐 Python module_file/dao/file_entry_dao.py)
//!
//! 根目录口径: pid 为 NULL 或空串均视为根级条目(与 Python 查询条件一致)。

use sea_orm::sea_query::{Expr, Func};
use sea_orm::{
    ColumnTrait, Condition, ConnectionTrait, DatabaseConnection, EntityTrait, PaginatorTrait,
    QueryFilter, QueryOrder, QuerySelect, Set,
};
use uuid::Uuid;

use crate::do_::entity::{file_content, file_entry};
use sea_orm::prelude::Json;

use common::utils::error::AppError;
use common::utils::pagination::PaginationParams;

use crate::do_::filesystem::{now_utc, tags_to_json, FileEntryCreate, FileEntryPatch};

/// 根级条目条件(pid IS NULL OR pid = '')
fn root_pid_cond() -> Condition {
    Condition::any()
        .add(file_entry::Column::Pid.is_null())
        .add(file_entry::Column::Pid.eq(""))
}

/// 按父目录构造条件(根目录时匹配 NULL/空串)
fn pid_cond(pid: Option<&str>) -> Condition {
    match pid {
        Some(p) => Condition::all().add(file_entry::Column::Pid.eq(p)),
        None => root_pid_cond(),
    }
}

/// 新增文件/目录记录(主键为 32 位小写 hex uuid, 与 Python uuid4().hex 一致)
///
/// :return: 新创建条目ID
pub async fn add(db: &DatabaseConnection, data: FileEntryCreate) -> Result<String, AppError> {
    let id = Uuid::new_v4().simple().to_string();
    let am = file_entry::ActiveModel {
        id: Set(id.clone()),
        pid: Set(data.pid),
        name: Set(data.name),
        logical_path: Set(data.logical_path),
        is_directory: Set(data.is_directory),
        content_hash: Set(data.content_hash),
        file_size_bytes: Set(data.file_size_bytes.map(|v| v as i32)),
        file_extension: Set(data.file_extension),
        mime_type: Set(data.mime_type),
        description: Set(data.description),
        tags: Set(Some(tags_to_json(&data.tags))),
        source_module: Set(data.source_module),
        user_id: Set(data.user_id),
        // Python 模型默认值: 条目有效 + 状态 SUCCESS
        is_active: Set(true),
        group_id: Set(None),
        entry_status: Set(Some(crate::do_::entity::sea_orm_active_enums::Taskstatus::Success)),
        created_at: Set(Some(now_utc())),
        updated_at: Set(now_utc()),
    };
    file_entry::Entity::insert(am).exec(db).await?;
    Ok(id)
}

/// 查询单个条目(不过滤 is_active, 与 Python session.get 口径一致)
pub async fn get(db: &DatabaseConnection, id: &str) -> Result<Option<file_entry::Model>, AppError> {
    Ok(file_entry::Entity::find_by_id(id.to_owned()).one(db).await?)
}

/// 条目 + 内容记录联合查询(下载/详情用; 对齐 Python get_file_entry_with_content 左联)
///
/// :return: (条目, 内容记录(条目无内容哈希或内容不存在时为 None))
pub async fn get_with_content(
    db: &DatabaseConnection,
    id: &str,
) -> Result<Option<(file_entry::Model, Option<file_content::Model>)>, AppError> {
    let Some(entry) = file_entry::Entity::find_by_id(id.to_owned()).one(db).await? else {
        return Ok(None);
    };
    // 左联等价实现: 按条目内容哈希取内容记录(缺失即 None)
    let content = match entry.content_hash.as_deref() {
        Some(h) => file_content::Entity::find_by_id(h.to_owned()).one(db).await?,
        None => None,
    };
    Ok(Some((entry, content)))
}

/// 逻辑删除条目(is_active = False)
pub async fn soft_delete(db: &DatabaseConnection, id: &str) -> Result<(), AppError> {
    file_entry::Entity::update_many()
        .col_expr(file_entry::Column::IsActive, Expr::value(false))
        .filter(file_entry::Column::Id.eq(id))
        .exec(db)
        .await?;
    Ok(())
}

/// 批量逻辑删除
pub async fn batch_soft_delete(db: &DatabaseConnection, ids: &[String]) -> Result<(), AppError> {
    if ids.is_empty() {
        return Ok(());
    }
    file_entry::Entity::update_many()
        .col_expr(file_entry::Column::IsActive, Expr::value(false))
        .filter(file_entry::Column::Id.is_in(ids.iter().cloned()))
        .exec(db)
        .await?;
    Ok(())
}

/// 部分更新条目记录(仅显式传入字段生效)
///
/// :raises: AppError::not_found 条目不存在
pub async fn update(db: &DatabaseConnection, id: &str, patch: FileEntryPatch) -> Result<(), AppError> {
    let mut stmt = file_entry::Entity::update_many()
        .col_expr(file_entry::Column::UpdatedAt, Expr::value(now_utc()));
    if let Some(v) = patch.name {
        stmt = stmt.col_expr(file_entry::Column::Name, Expr::value(v));
    }
    if let Some(v) = patch.logical_path {
        stmt = stmt.col_expr(file_entry::Column::LogicalPath, Expr::value(v));
    }
    if let Some(v) = patch.pid {
        // 双层 Option: Some(None) 表示置空(移回根目录)
        stmt = stmt.col_expr(file_entry::Column::Pid, Expr::value(v));
    }
    if let Some(v) = patch.description {
        stmt = stmt.col_expr(file_entry::Column::Description, Expr::value(v));
    }
    if let Some(v) = patch.tags {
        let json: Json = tags_to_json(&v);
        stmt = stmt.col_expr(file_entry::Column::Tags, Expr::value(json));
    }
    let result = stmt
        .filter(file_entry::Column::Id.eq(id))
        .exec(db)
        .await?;
    if result.rows_affected == 0 {
        return Err(AppError::not_found(format!("未找到ID为 {id} 的文件")));
    }
    Ok(())
}

/// 名称模糊过滤条件(大小写不敏感, 与 Python ilike 一致; LOWER(col) LIKE '%kw%' 跨库等价)
fn name_like_cond(name: &str) -> sea_orm::sea_query::SimpleExpr {
    Expr::expr(Func::lower(Expr::col(file_entry::Column::Name)))
        .like(format!("%{}%", name.to_lowercase()))
}

/// 分页查询指定目录下的条目(目录排前, 名称排序)
pub async fn list_by_pid(
    db: &DatabaseConnection,
    pid: Option<&str>,
    pagination: &PaginationParams,
    name: Option<&str>,
) -> Result<Vec<file_entry::Model>, AppError> {
    let mut cond = Condition::all()
        .add(file_entry::Column::IsActive.eq(true))
        .add(pid_cond(pid));
    if let Some(n) = name {
        if !n.is_empty() {
            cond = cond.add(name_like_cond(n));
        }
    }
    let rows = file_entry::Entity::find()
        .filter(cond)
        .order_by_desc(file_entry::Column::IsDirectory)
        .order_by_asc(file_entry::Column::Name)
        .offset(pagination.offset())
        .limit(pagination.limit())
        .all(db)
        .await?;
    Ok(rows)
}

/// 统计指定目录下的条目总数
pub async fn count_by_pid(
    db: &DatabaseConnection,
    pid: Option<&str>,
    name: Option<&str>,
) -> Result<u64, AppError> {
    let mut cond = Condition::all()
        .add(file_entry::Column::IsActive.eq(true))
        .add(pid_cond(pid));
    if let Some(n) = name {
        if !n.is_empty() {
            cond = cond.add(name_like_cond(n));
        }
    }
    Ok(file_entry::Entity::find().filter(cond).count(db).await?)
}

/// 检查指定目录下是否已存在同名活跃条目
///
/// :param exclude_id: 排除自身ID(重命名场景)
pub async fn exists_by_pid_name(
    db: &DatabaseConnection,
    pid: Option<&str>,
    name: &str,
    exclude_id: Option<&str>,
) -> Result<bool, AppError> {
    let mut cond = Condition::all()
        .add(file_entry::Column::IsActive.eq(true))
        .add(pid_cond(pid))
        .add(file_entry::Column::Name.eq(name));
    if let Some(exclude) = exclude_id {
        cond = cond.add(file_entry::Column::Id.ne(exclude));
    }
    Ok(file_entry::Entity::find().filter(cond).count(db).await? > 0)
}

/// 按父目录与名称精确查询活跃条目(幂等建目录场景)
pub async fn get_by_pid_name(
    db: &DatabaseConnection,
    pid: Option<&str>,
    name: &str,
) -> Result<Option<file_entry::Model>, AppError> {
    let cond = Condition::all()
        .add(file_entry::Column::IsActive.eq(true))
        .add(pid_cond(pid))
        .add(file_entry::Column::Name.eq(name));
    Ok(file_entry::Entity::find().filter(cond).one(db).await?)
}

/// 查询指定目录下的全部子目录(不分页, 用于目录树选择)
pub async fn list_dirs_by_pid(
    db: &DatabaseConnection,
    pid: Option<&str>,
) -> Result<Vec<file_entry::Model>, AppError> {
    let cond = Condition::all()
        .add(file_entry::Column::IsActive.eq(true))
        .add(pid_cond(pid))
        .add(file_entry::Column::IsDirectory.eq(true));
    let rows = file_entry::Entity::find()
        .filter(cond)
        .order_by_asc(file_entry::Column::Name)
        .all(db)
        .await?;
    Ok(rows)
}

/// 批量更新子树逻辑路径前缀(目录重命名/移动时同步子孙路径)
///
/// 应用层逐条替换前缀(避免方言相关的 SQL 字符串函数, 与 Python 实现一致)
/// :return: 更新的条目数量
pub async fn update_children_path_prefix(
    db: &DatabaseConnection,
    old_prefix: &str,
    new_prefix: &str,
) -> Result<usize, AppError> {
    let cond = Condition::all()
        .add(file_entry::Column::IsActive.eq(true))
        .add(Expr::col(file_entry::Column::LogicalPath).like(format!("{old_prefix}/%")));
    let rows = file_entry::Entity::find().filter(cond).all(db).await?;
    let prefix_len = old_prefix.len();
    for row in &rows {
        let new_path = format!("{}{}", new_prefix, &row.logical_path[prefix_len..]);
        file_entry::Entity::update_many()
            .col_expr(file_entry::Column::LogicalPath, Expr::value(new_path))
            .filter(file_entry::Column::Id.eq(&row.id))
            .exec(db)
            .await?;
    }
    Ok(rows.len())
}

/// 按条目类型统计活跃条目(存储统计用, 口径与列表页一致)
///
/// :return: (条目总数, 文件数, 目录数) 均仅统计 is_active=true
pub async fn count_by_type(db: &DatabaseConnection) -> Result<(i64, i64, i64), AppError> {
    let active = Condition::all().add(file_entry::Column::IsActive.eq(true));
    let entry_total = file_entry::Entity::find().filter(active.clone()).count(db).await? as i64;
    let file_cond = Condition::all()
        .add(file_entry::Column::IsActive.eq(true))
        .add(file_entry::Column::IsDirectory.eq(false));
    let file_total = file_entry::Entity::find().filter(file_cond).count(db).await? as i64;
    Ok((entry_total, file_total, entry_total - file_total))
}

/// 查询业务模块的顶层根目录(顶层条目且 source_module 精确匹配)
///
/// 按 source_module 而非名称匹配, 目录被改名后仍能找到
pub async fn get_module_root(
    db: &DatabaseConnection,
    module_key: &str,
) -> Result<Option<file_entry::Model>, AppError> {
    let cond = Condition::all()
        .add(file_entry::Column::IsActive.eq(true))
        .add(root_pid_cond())
        .add(file_entry::Column::SourceModule.eq(module_key));
    Ok(file_entry::Entity::find().filter(cond).one(db).await?)
}

/// 按逻辑路径精确查询活跃条目(路径操作入口)
pub async fn get_by_logical_path(
    db: &DatabaseConnection,
    logical_path: &str,
) -> Result<Option<file_entry::Model>, AppError> {
    let cond = Condition::all()
        .add(file_entry::Column::IsActive.eq(true))
        .add(file_entry::Column::LogicalPath.eq(logical_path));
    Ok(file_entry::Entity::find().filter(cond).one(db).await?)
}

/// 全树模糊搜索条目(匹配名称或逻辑路径, 目录排前, 路径排序)
pub async fn search(
    db: &DatabaseConnection,
    keyword: &str,
    pagination: &PaginationParams,
) -> Result<Vec<file_entry::Model>, AppError> {
    let like = format!("%{}%", keyword.to_lowercase());
    let cond = Condition::all()
        .add(file_entry::Column::IsActive.eq(true))
        .add(
            Expr::expr(Func::lower(Expr::col(file_entry::Column::Name)))
                .like(like.clone())
                .or(Expr::expr(Func::lower(Expr::col(file_entry::Column::LogicalPath))).like(like)),
        );
    let rows = file_entry::Entity::find()
        .filter(cond)
        .order_by_desc(file_entry::Column::IsDirectory)
        .order_by_asc(file_entry::Column::LogicalPath)
        .offset(pagination.offset())
        .limit(pagination.limit())
        .all(db)
        .await?;
    Ok(rows)
}

/// 统计全树模糊搜索命中条目数
pub async fn count_search(db: &DatabaseConnection, keyword: &str) -> Result<u64, AppError> {
    let like = format!("%{}%", keyword.to_lowercase());
    let cond = Condition::all()
        .add(file_entry::Column::IsActive.eq(true))
        .add(
            Expr::expr(Func::lower(Expr::col(file_entry::Column::Name)))
                .like(like.clone())
                .or(Expr::expr(Func::lower(Expr::col(file_entry::Column::LogicalPath))).like(like)),
        );
    Ok(file_entry::Entity::find().filter(cond).count(db).await?)
}

/// 查询指定目录下的全部直接子项(目录复制/递归遍历用, 不分页)
pub async fn list_children(
    db: &DatabaseConnection,
    pid: Option<&str>,
) -> Result<Vec<file_entry::Model>, AppError> {
    let cond = Condition::all()
        .add(file_entry::Column::IsActive.eq(true))
        .add(pid_cond(pid));
    let rows = file_entry::Entity::find()
        .filter(cond)
        .order_by_desc(file_entry::Column::IsDirectory)
        .order_by_asc(file_entry::Column::Name)
        .all(db)
        .await?;
    Ok(rows)
}

/// 获取目录及其所有子项的 ID 列表(递归 CTE, 兼容 SQLite/PostgreSQL)
pub async fn get_subtree_ids(
    db: &DatabaseConnection,
    folder_id: &str,
) -> Result<Vec<String>, AppError> {
    let sql = r#"
        WITH RECURSIVE subtree AS (
            SELECT id FROM file_entry
            WHERE id = $1 AND is_active = TRUE
            UNION ALL
            SELECT fe.id FROM file_entry fe
            INNER JOIN subtree s ON fe.pid = s.id
            WHERE fe.is_active = TRUE
        )
        SELECT id FROM subtree
    "#;
    let backend = db.get_database_backend();
    let stmt = sea_orm::Statement::from_sql_and_values(backend, sql, [folder_id.into()]);
    let rows = db.query_all(stmt).await?;
    let mut ids = Vec::with_capacity(rows.len());
    for row in rows {
        ids.push(row.try_get("", "id")?);
    }
    Ok(ids)
}

/// 根据 ID 列表获取去重后的 content_hash 列表(仅非目录项)
pub async fn get_content_hashes_by_ids(
    db: &DatabaseConnection,
    ids: &[String],
) -> Result<Vec<String>, AppError> {
    if ids.is_empty() {
        return Ok(Vec::new());
    }
    let cond = Condition::all()
        .add(file_entry::Column::Id.is_in(ids.iter().cloned()))
        .add(file_entry::Column::IsDirectory.eq(false))
        .add(file_entry::Column::ContentHash.is_not_null());
    // select_only: 仅选 content_hash 单列做 DISTINCT(否则默认全列参与去重,
    // PostgreSQL 对 json 列无等值运算符会报错)
    let rows = file_entry::Entity::find()
        .filter(cond)
        .select_only()
        .column(file_entry::Column::ContentHash)
        .distinct()
        .into_tuple::<Option<String>>()
        .all(db)
        .await?;
    Ok(rows.into_iter().flatten().collect())
}
