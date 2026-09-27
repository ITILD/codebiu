//! 文件内容数据访问(对齐 Python module_file/dao/file_content_dao.py)
//!
//! file_content 按内容哈希(SHA-256)全局去重, 引用计数管理物理文件生命周期。

use sea_orm::sea_query::Expr;
use sea_orm::{
    ActiveEnum, ColumnTrait, DatabaseConnection, EntityTrait, QueryFilter, QuerySelect, Set,
};

use crate::do_::entity::file_content;
use crate::do_::entity::sea_orm_active_enums::Taskstatus;

use common::utils::error::AppError;

use crate::do_::filesystem::{FileContentCreate, FileContentPatch};

/// 新增文件内容记录
///
/// :return: 新创建内容的哈希值
pub async fn add(db: &DatabaseConnection, data: FileContentCreate) -> Result<String, AppError> {
    let am = file_content::ActiveModel {
        content_hash: Set(data.content_hash.clone()),
        physical_storage: Set(Some(data.physical_storage)),
        file_size_bytes: Set(Some(data.file_size_bytes as i32)),
        // Python 模型默认值: 引用计数 0 + 状态 PENDING
        ref_count: Set(0),
        storage_type: Set(Some(data.storage_type)),
        content_status: Set(Some(Taskstatus::Pending)),
    };
    file_content::Entity::insert(am).exec(db).await?;
    Ok(data.content_hash)
}

/// 删除内容记录(物理文件已归零清理后调用)
///
/// :raises: AppError::not_found 未找到对应哈希的内容记录
pub async fn delete(db: &DatabaseConnection, content_hash: &str) -> Result<(), AppError> {
    let result = file_content::Entity::delete_by_id(content_hash.to_owned())
        .exec(db)
        .await?;
    if result.rows_affected == 0 {
        return Err(AppError::not_found(format!(
            "未找到hash值为 {content_hash} 的文件"
        )));
    }
    Ok(())
}

/// 更新内容记录(物理存储迁移/归位校正; 仅显式传入字段生效)
///
/// :raises: AppError::not_found 未找到对应哈希的内容记录
pub async fn update(
    db: &DatabaseConnection,
    content_hash: &str,
    patch: FileContentPatch,
) -> Result<(), AppError> {
    let mut stmt = file_content::Entity::update_many();
    if let Some(v) = patch.physical_storage {
        stmt = stmt.col_expr(file_content::Column::PhysicalStorage, Expr::value(v));
    }
    if let Some(v) = patch.file_size_bytes {
        stmt = stmt.col_expr(file_content::Column::FileSizeBytes, Expr::value(v as i32));
    }
    if let Some(v) = patch.storage_type {
        // 枚举列显式 CAST(PG 自定义枚举类型不接受裸 text 参数)
        stmt = stmt.col_expr(file_content::Column::StorageType, v.as_enum());
    }
    let result = stmt
        .filter(file_content::Column::ContentHash.eq(content_hash))
        .exec(db)
        .await?;
    if result.rows_affected == 0 {
        return Err(AppError::not_found(format!(
            "未找到hash值为 {content_hash} 的文件"
        )));
    }
    Ok(())
}

/// 按内容哈希查询内容记录
pub async fn get_by_content_hash(
    db: &DatabaseConnection,
    content_hash: &str,
) -> Result<Option<file_content::Model>, AppError> {
    Ok(file_content::Entity::find_by_id(content_hash.to_owned())
        .one(db)
        .await?)
}

/// 原子地变更文件引用计数(仅对已完成文件)
///
/// - change > 0 时, 同时将 content_status 置为 SUCCESS(确保文件可用)
/// - change <= 0 时, 仅修改 ref_count, 不触碰 status
/// :raises: AppError::not_found 未找到可引用的文件
pub async fn ref_count_change(
    db: &DatabaseConnection,
    content_hash: &str,
    change: i64,
) -> Result<(), AppError> {
    let mut stmt = file_content::Entity::update_many().col_expr(
        file_content::Column::RefCount,
        Expr::col(file_content::Column::RefCount).add(change as i32),
    );
    if change > 0 {
        // 枚举列显式 CAST(PG 自定义枚举类型 taskstatus 不接受裸 text 参数)
        stmt = stmt.col_expr(file_content::Column::ContentStatus, Taskstatus::Success.as_enum());
    }
    let result = stmt
        .filter(file_content::Column::ContentHash.eq(content_hash))
        .exec(db)
        .await?;
    if result.rows_affected == 0 {
        return Err(AppError::not_found(format!(
            "未找到可引用的文件: {content_hash}"
        )));
    }
    Ok(())
}

/// 替换内容记录主键哈希(分片上传完成时临时标识 → 真实SHA-256)
///
/// :raises: AppError::not_found 未找到对应哈希的内容记录
pub async fn replace_content_hash(
    db: &DatabaseConnection,
    old_hash: &str,
    new_hash: &str,
    physical_storage: &str,
) -> Result<(), AppError> {
    let result = file_content::Entity::update_many()
        .col_expr(file_content::Column::ContentHash, Expr::value(new_hash))
        .col_expr(
            file_content::Column::PhysicalStorage,
            Expr::value(physical_storage),
        )
        .filter(file_content::Column::ContentHash.eq(old_hash))
        .exec(db)
        .await?;
    if result.rows_affected == 0 {
        return Err(AppError::not_found(format!(
            "未找到hash值为 {old_hash} 的文件"
        )));
    }
    Ok(())
}

/// 查询全部物理内容记录(存储迁移遍历用)
pub async fn list_all(db: &DatabaseConnection) -> Result<Vec<file_content::Model>, AppError> {
    let rows = file_content::Entity::find().all(db).await?;
    Ok(rows)
}

/// 物理内容统计(存储统计用)
///
/// :return: (内容记录总数, 物理存储总占用字节)
pub async fn stats(db: &DatabaseConnection) -> Result<(i64, i64), AppError> {
    let row = file_content::Entity::find()
        .select_only()
        .column_as(Expr::col(file_content::Column::ContentHash).count(), "cnt")
        .column_as(
            Expr::cust("coalesce(sum(file_size_bytes), 0)"),
            "total_bytes",
        )
        .into_tuple::<(i64, i64)>()
        .one(db)
        .await?
        .unwrap_or((0, 0));
    Ok(row)
}
