//! 记账数据访问(对齐 Python module_site/dao/ledger.py)
//!
//! 写操作全部按 user_id 归属隔离; 统计聚合查询返回原始行, 组装在 services 层。

use chrono::NaiveDate;
use sea_orm::sea_query::{Expr, SimpleExpr};
use sea_orm::{
    ActiveModelTrait, ColumnTrait, ConnectionTrait, DatabaseConnection, DbBackend, EntityTrait,
    PaginatorTrait, QueryFilter, QueryOrder, QuerySelect, Select, Set,
};
use uuid::Uuid;

use crate::do_::entity::ledger_record;

use common::utils::error::AppError;
use common::utils::pagination::PaginationParams;

use crate::do_::ledger::{LedgerFlow, LedgerRecordCreate, LedgerRecordUpdate};
use crate::do_::now_utc;

/// 新增记账记录(归属当前用户)
///
/// :return: 新建记录ID
pub async fn add(
    db: &DatabaseConnection,
    data: LedgerRecordCreate,
    user_id: &str,
) -> Result<String, AppError> {
    let id = Uuid::new_v4().simple().to_string();
    let am = ledger_record::ActiveModel {
        amount: Set(data.amount),
        // 未传字段取 Python 模型默认值
        flow_type: Set(data.flow_type.unwrap_or(LedgerFlow::Expense).as_str().to_string()),
        category: Set(data.category),
        note: Set(data.note),
        occurred_at: Set(Some(
            data.occurred_at.unwrap_or_else(|| chrono::Utc::now().date_naive()),
        )),
        id: Set(id.clone()),
        user_id: Set(user_id.to_string()),
        created_at: Set(Some(now_utc())),
        updated_at: Set(now_utc()),
    };
    am.insert(db).await?;
    Ok(id)
}

/// 查询单条记账记录(不限归属, 由服务层判定可见性)
pub async fn get(
    db: &DatabaseConnection,
    record_id: &str,
) -> Result<Option<ledger_record::Model>, AppError> {
    Ok(ledger_record::Entity::find_by_id(record_id.to_owned())
        .one(db)
        .await?)
}

/// 直接更新本人记账记录(不先查询, 仅显式传入字段生效)
///
/// :raises: AppError::not_found 记录不存在或不属于当前用户
pub async fn update(
    db: &DatabaseConnection,
    record_id: &str,
    data: LedgerRecordUpdate,
    user_id: &str,
) -> Result<(), AppError> {
    let mut update = ledger_record::Entity::update_many()
        .col_expr(ledger_record::Column::UpdatedAt, Expr::value(now_utc()));
    if let Some(v) = data.amount {
        update = update.col_expr(ledger_record::Column::Amount, Expr::value(v));
    }
    if let Some(v) = data.flow_type {
        update = update.col_expr(
            ledger_record::Column::FlowType,
            Expr::value(v.as_str().to_string()),
        );
    }
    if let Some(v) = data.category {
        update = update.col_expr(ledger_record::Column::Category, Expr::value(v));
    }
    if let Some(v) = data.note {
        update = update.col_expr(ledger_record::Column::Note, Expr::value(v));
    }
    if let Some(v) = data.occurred_at {
        update = update.col_expr(ledger_record::Column::OccurredAt, Expr::value(v));
    }
    let result = update
        .filter(ledger_record::Column::Id.eq(record_id))
        .filter(ledger_record::Column::UserId.eq(user_id))
        .exec(db)
        .await?;
    if result.rows_affected == 0 {
        return Err(AppError::not_found(format!(
            "未找到ID为 {record_id} 的记账记录"
        )));
    }
    Ok(())
}

/// 删除本人记账记录
///
/// :raises: AppError::not_found 记录不存在或不属于当前用户
pub async fn delete(
    db: &DatabaseConnection,
    record_id: &str,
    user_id: &str,
) -> Result<(), AppError> {
    let result = ledger_record::Entity::delete_many()
        .filter(ledger_record::Column::Id.eq(record_id))
        .filter(ledger_record::Column::UserId.eq(user_id))
        .exec(db)
        .await?;
    if result.rows_affected == 0 {
        return Err(AppError::not_found(format!(
            "未找到ID为 {record_id} 的记账记录"
        )));
    }
    Ok(())
}

/// 月份匹配谓词(跨库: pg to_char / sqlite strftime; occurred_at 为 Date 列)
fn month_eq(db: &DatabaseConnection, month: &str) -> SimpleExpr {
    match db.get_database_backend() {
        DbBackend::Postgres => Expr::cust("to_char(occurred_at, 'YYYY-MM')").eq(month.to_string()),
        _ => Expr::cust("strftime('%Y-%m', occurred_at)").eq(month.to_string()),
    }
}

/// 本人记录列表查询(月份/方向/分类过滤, 列表与计数共用)
fn mine_select(
    db: &DatabaseConnection,
    user_id: &str,
    month: Option<&str>,
    flow_type: Option<&str>,
    category: Option<&str>,
) -> Select<ledger_record::Entity> {
    let mut select =
        ledger_record::Entity::find().filter(ledger_record::Column::UserId.eq(user_id));
    if let Some(m) = month {
        select = select.filter(month_eq(db, m));
    }
    if let Some(f) = flow_type {
        select = select.filter(ledger_record::Column::FlowType.eq(f));
    }
    if let Some(c) = category {
        select = select.filter(ledger_record::Column::Category.contains(c));
    }
    select
}

/// 分页查询本人记账记录(按记账日期/创建时间倒序)
pub async fn list_mine(
    db: &DatabaseConnection,
    pagination: &PaginationParams,
    user_id: &str,
    month: Option<&str>,
    flow_type: Option<&str>,
    category: Option<&str>,
) -> Result<Vec<ledger_record::Model>, AppError> {
    Ok(mine_select(db, user_id, month, flow_type, category)
        .order_by_desc(ledger_record::Column::OccurredAt)
        .order_by_desc(ledger_record::Column::CreatedAt)
        .offset(pagination.offset())
        .limit(pagination.limit())
        .all(db)
        .await?)
}

/// 统计本人记账记录总数(与列表过滤条件一致)
pub async fn count_mine(
    db: &DatabaseConnection,
    user_id: &str,
    month: Option<&str>,
    flow_type: Option<&str>,
    category: Option<&str>,
) -> Result<i64, AppError> {
    let total = mine_select(db, user_id, month, flow_type, category)
        .count(db)
        .await?;
    Ok(total as i64)
}

/// 周期内收/支合计(group by flow_type)
pub async fn sum_by_flow(
    db: &DatabaseConnection,
    user_id: &str,
    period_start: NaiveDate,
    period_end: NaiveDate,
) -> Result<Vec<(String, Option<f64>)>, AppError> {
    Ok(ledger_record::Entity::find()
        .select_only()
        .column(ledger_record::Column::FlowType)
        .column_as(Expr::col(ledger_record::Column::Amount).sum(), "total")
        .filter(ledger_record::Column::UserId.eq(user_id))
        .filter(ledger_record::Column::OccurredAt.gte(period_start))
        .filter(ledger_record::Column::OccurredAt.lt(period_end))
        .group_by(ledger_record::Column::FlowType)
        .into_tuple::<(String, Option<f64>)>()
        .all(db)
        .await?)
}

/// 周期内支出分类饼图(group by category, 按金额降序)
pub async fn category_pie(
    db: &DatabaseConnection,
    user_id: &str,
    period_start: NaiveDate,
    period_end: NaiveDate,
) -> Result<Vec<(String, Option<f64>, i64)>, AppError> {
    Ok(ledger_record::Entity::find()
        .select_only()
        .column(ledger_record::Column::Category)
        .column_as(Expr::col(ledger_record::Column::Amount).sum(), "total")
        .column_as(Expr::col(ledger_record::Column::Id).count(), "count")
        .filter(ledger_record::Column::UserId.eq(user_id))
        .filter(ledger_record::Column::FlowType.eq(LedgerFlow::Expense.as_str()))
        .filter(ledger_record::Column::OccurredAt.gte(period_start))
        .filter(ledger_record::Column::OccurredAt.lt(period_end))
        .group_by(ledger_record::Column::Category)
        .order_by_desc(Expr::col(ledger_record::Column::Amount).sum())
        .into_tuple::<(String, Option<f64>, i64)>()
        .all(db)
        .await?)
}

/// 趋势行(按月份聚合收支, 月度近6月 / 年度全年12月; 缺失月份由服务层补零)
pub async fn monthly_trend(
    db: &DatabaseConnection,
    user_id: &str,
    trend_start: NaiveDate,
    period_end: NaiveDate,
) -> Result<Vec<(String, String, Option<f64>)>, AppError> {
    // 月份表达式跨库: to_char / strftime
    let month_expr = match db.get_database_backend() {
        DbBackend::Postgres => Expr::cust("to_char(occurred_at, 'YYYY-MM')"),
        _ => Expr::cust("strftime('%Y-%m', occurred_at)"),
    };
    Ok(ledger_record::Entity::find()
        .select_only()
        .column_as(month_expr.clone(), "month")
        .column(ledger_record::Column::FlowType)
        .column_as(Expr::col(ledger_record::Column::Amount).sum(), "total")
        .filter(ledger_record::Column::UserId.eq(user_id))
        .filter(ledger_record::Column::OccurredAt.gte(trend_start))
        .filter(ledger_record::Column::OccurredAt.lt(period_end))
        .group_by(month_expr.clone())
        .group_by(ledger_record::Column::FlowType)
        .order_by_asc(month_expr)
        .into_tuple::<(String, String, Option<f64>)>()
        .all(db)
        .await?)
}
