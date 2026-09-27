//! 文档/分块 DAO(对齐 Python module_rag/dao/project_document.py、
//! project_document_chunk.py; 分块落关系表, 向量字段暂缺)

use sea_orm::{
    ActiveModelTrait, ColumnTrait, Condition, DatabaseConnection, DbErr, EntityTrait,
    IntoActiveModel, PaginatorTrait, QueryFilter, QueryOrder, Set,
};

use crate::do_::entity::{project_document, project_document_chunk};

// ==================== 文档 ====================

/// 新增文档记录
pub async fn document_add(
    db: &DatabaseConnection,
    am: project_document::ActiveModel,
) -> Result<project_document::Model, DbErr> {
    am.insert(db).await
}

/// 按ID获取文档
pub async fn document_get(
    db: &DatabaseConnection,
    id: &str,
) -> Result<Option<project_document::Model>, DbErr> {
    project_document::Entity::find_by_id(id.to_owned()).one(db).await
}

/// 更新文档记录(仅 Some 字段)
pub async fn document_update(
    db: &DatabaseConnection,
    model: project_document::Model,
    name: Option<String>,
    description: Option<Option<String>>,
    parse_status: Option<String>,
    chunk_count: Option<i32>,
    error_message: Option<Option<String>>,
    parse_steps: Option<sea_orm::prelude::Json>,
) -> Result<project_document::Model, DbErr> {
    let mut am = model.into_active_model();
    if let Some(v) = name {
        am.name = Set(v);
    }
    if let Some(v) = description {
        am.description = Set(v);
    }
    if let Some(v) = parse_status {
        am.parse_status = Set(v);
    }
    if let Some(v) = chunk_count {
        am.chunk_count = Set(v);
    }
    if let Some(v) = error_message {
        am.error_message = Set(v);
    }
    if let Some(v) = parse_steps {
        am.parse_steps = Set(v);
    }
    am.updated_at = Set(chrono::Utc::now().into());
    am.update(db).await
}

/// 删除文档记录
pub async fn document_delete(db: &DatabaseConnection, id: &str) -> Result<(), DbErr> {
    project_document::Entity::delete_by_id(id.to_owned()).exec(db).await?;
    Ok(())
}

/// 删除项目全部文档记录, 返回删除数
pub async fn document_delete_by_project(db: &DatabaseConnection, project_id: &str) -> Result<u64, DbErr> {
    let res = project_document::Entity::delete_many()
        .filter(project_document::Column::ProjectId.eq(project_id))
        .exec(db)
        .await?;
    Ok(res.rows_affected)
}

/// 项目文档列表(可选名称模糊/解析状态过滤, 创建时间倒序)
pub async fn document_list_by_project(
    db: &DatabaseConnection,
    project_id: &str,
    name: Option<&str>,
    parse_status: Option<&str>,
) -> Result<Vec<project_document::Model>, DbErr> {
    let mut cond = Condition::all().add(project_document::Column::ProjectId.eq(project_id));
    if let Some(n) = name.filter(|v| !v.is_empty()) {
        cond = cond.add(project_document::Column::Name.contains(n));
    }
    if let Some(s) = parse_status.filter(|v| !v.is_empty()) {
        cond = cond.add(project_document::Column::ParseStatus.eq(s));
    }
    project_document::Entity::find()
        .filter(cond)
        .order_by_desc(project_document::Column::CreatedAt)
        .all(db)
        .await
}

/// 项目全部文档(项目级联删除用)
pub async fn document_list_all_by_project(
    db: &DatabaseConnection,
    project_id: &str,
) -> Result<Vec<project_document::Model>, DbErr> {
    project_document::Entity::find()
        .filter(project_document::Column::ProjectId.eq(project_id))
        .all(db)
        .await
}

/// 项目文档计数(重向量化进度统计用)
pub async fn document_count_by_project(db: &DatabaseConnection, project_id: &str) -> Result<u64, DbErr> {
    project_document::Entity::find()
        .filter(project_document::Column::ProjectId.eq(project_id))
        .count(db)
        .await
}

// ==================== 分块 ====================

/// 批量写入分块(替换式: 先清后写由服务层调度)
pub async fn chunk_add_batch(
    db: &DatabaseConnection,
    chunks: Vec<project_document_chunk::ActiveModel>,
) -> Result<(), DbErr> {
    if chunks.is_empty() {
        return Ok(());
    }
    project_document_chunk::Entity::insert_many(chunks).exec(db).await?;
    Ok(())
}

/// 删除文档全部分块
pub async fn chunk_delete_by_document(db: &DatabaseConnection, document_id: &str) -> Result<(), DbErr> {
    project_document_chunk::Entity::delete_many()
        .filter(project_document_chunk::Column::DocumentId.eq(document_id))
        .exec(db)
        .await?;
    Ok(())
}

/// 删除项目全部分块(项目级联删除)
pub async fn chunk_delete_by_project(db: &DatabaseConnection, project_id: &str) -> Result<(), DbErr> {
    project_document_chunk::Entity::delete_many()
        .filter(project_document_chunk::Column::ProjectId.eq(project_id))
        .exec(db)
        .await?;
    Ok(())
}

/// 文档分块列表(按 sort 升序, 检索退化场景全文扫描用)
pub async fn chunk_list_by_document(
    db: &DatabaseConnection,
    document_id: &str,
) -> Result<Vec<project_document_chunk::Model>, DbErr> {
    project_document_chunk::Entity::find()
        .filter(project_document_chunk::Column::DocumentId.eq(document_id))
        .order_by_asc(project_document_chunk::Column::Sort)
        .all(db)
        .await
}
