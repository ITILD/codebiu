//! 任务队列数据访问(对齐 Python module_task/dao/task.py)

use common::utils::error::AppError;
use common::utils::pagination::PaginationParams;
use sea_orm::sea_query::Expr;
use sea_orm::{
    ActiveModelTrait, ColumnTrait, Condition, DatabaseConnection, EntityTrait, PaginatorTrait,
    QueryFilter, QueryOrder, QuerySelect, Set,
};

use crate::do_::entity::task_queue;
use crate::do_::task::{now_utc, STATUS_PENDING, STATUS_RUNNING};

/// 过滤条件构造(keyword 名称模糊/状态精确/类型精确; 空串视为不过滤, 与 Python 真值判断一致)
fn filter_cond(
    keyword: Option<&str>,
    status: Option<&str>,
    task_type: Option<&str>,
) -> Condition {
    let mut cond = Condition::all();
    if let Some(k) = keyword.filter(|s| !s.is_empty()) {
        cond = cond.add(task_queue::Column::Name.contains(k));
    }
    if let Some(s) = status.filter(|s| !s.is_empty()) {
        cond = cond.add(task_queue::Column::Status.eq(s));
    }
    if let Some(t) = task_type.filter(|s| !s.is_empty()) {
        cond = cond.add(task_queue::Column::TaskType.eq(t));
    }
    cond
}

/// 新增任务记录(status=pending; 主键由 service 生成后随 ActiveModel 传入)
pub async fn add(db: &DatabaseConnection, task: task_queue::ActiveModel) -> Result<(), AppError> {
    task.insert(db).await?;
    Ok(())
}

/// 按ID查询任务
pub async fn get(
    db: &DatabaseConnection,
    task_id: &str,
) -> Result<Option<task_queue::Model>, AppError> {
    Ok(task_queue::Entity::find_by_id(task_id.to_owned()).one(db).await?)
}

/// 保存任务对象变更(service 修改字段后传入; 仅写入显式 Set 的字段, updated_at 恒刷新)
pub async fn update(
    db: &DatabaseConnection,
    mut task: task_queue::ActiveModel,
) -> Result<(), AppError> {
    task.updated_at = Set(now_utc());
    task.update(db).await?;
    Ok(())
}

/// 删除任务记录(不存在 → 404, 文案与 Python dao.delete 一致)
pub async fn delete(db: &DatabaseConnection, task_id: &str) -> Result<(), AppError> {
    let Some(task) = get(db, task_id).await? else {
        return Err(AppError::not_found(format!("未找到ID为 {task_id} 的任务")));
    };
    task_queue::Entity::delete_by_id(task.id).exec(db).await?;
    Ok(())
}

/// 分页查询任务列表(创建时间倒序)
pub async fn list_page(
    db: &DatabaseConnection,
    pagination: &PaginationParams,
    keyword: Option<&str>,
    status: Option<&str>,
    task_type: Option<&str>,
) -> Result<Vec<task_queue::Model>, AppError> {
    let rows = task_queue::Entity::find()
        .filter(filter_cond(keyword, status, task_type))
        .order_by_desc(task_queue::Column::CreatedAt)
        .offset(pagination.offset())
        .limit(pagination.limit())
        .all(db)
        .await?;
    Ok(rows)
}

/// 统计任务总数(与列表过滤条件一致)
pub async fn count(
    db: &DatabaseConnection,
    keyword: Option<&str>,
    status: Option<&str>,
    task_type: Option<&str>,
) -> Result<u64, AppError> {
    Ok(task_queue::Entity::find()
        .filter(filter_cond(keyword, status, task_type))
        .count(db)
        .await?)
}

/// 按状态分组统计任务数
///
/// :return: [("pending", n), ("running", n), ...]
pub async fn stats(db: &DatabaseConnection) -> Result<Vec<(String, i64)>, AppError> {
    let rows = task_queue::Entity::find()
        .select_only()
        .column(task_queue::Column::Status)
        .column_as(Expr::col(task_queue::Column::Id).count(), "num")
        .group_by(task_queue::Column::Status)
        .into_tuple::<(String, i64)>()
        .all(db)
        .await?;
    Ok(rows)
}

/// 原子认领: pending → running(返回是否认领成功)
///
/// 防 worker 自愈与创建派发协程并发双执行; 认领失败说明已被取消或已被认领。
pub async fn claim_pending(db: &DatabaseConnection, task_id: &str) -> Result<bool, AppError> {
    let result = task_queue::Entity::update_many()
        .col_expr(task_queue::Column::Status, Expr::value(STATUS_RUNNING))
        .col_expr(task_queue::Column::UpdatedAt, Expr::value(now_utc()))
        .filter(task_queue::Column::Id.eq(task_id))
        .filter(task_queue::Column::Status.eq(STATUS_PENDING))
        .exec(db)
        .await?;
    Ok(result.rows_affected > 0)
}

/// 自愈扫描: 创建早于 cutoff 仍为 pending 的遗留任务(进程重启丢失后台协程的场景)
///
/// 对齐 Python recover_pending_tasks(pending + created_at < cutoff; celery_task_id 恒为空故省略)
pub async fn list_stale_pending(
    db: &DatabaseConnection,
    cutoff: sea_orm::prelude::DateTimeWithTimeZone,
) -> Result<Vec<task_queue::Model>, AppError> {
    let rows = task_queue::Entity::find()
        .filter(task_queue::Column::Status.eq(STATUS_PENDING))
        .filter(task_queue::Column::CreatedAt.lt(cutoff))
        .order_by_asc(task_queue::Column::CreatedAt)
        .all(db)
        .await?;
    Ok(rows)
}
