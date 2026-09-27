//! 记账服务: 收支记录管理 + 月度统计(概览/饼图/趋势)

use std::collections::HashMap;

use chrono::{Datelike, NaiveDate};
use sea_orm::DatabaseConnection;

use crate::do_::entity::ledger_record;

use common::utils::error::AppError;
use common::utils::pagination::{PaginationParams, PaginationResponse};

use crate::dao;
use crate::do_::ledger::{
    CategoryStat, LedgerRecordCreate, LedgerRecordUpdate, LedgerStats, MonthTrend,
};

/// 保留两位小数(金额展示与 Python round(x, 2) 对齐)
fn round2(v: f64) -> f64 {
    (v * 100.0).round() / 100.0
}

/// 新增记账记录(归属当前用户)
///
/// :return: 新建记录ID
pub async fn add(
    db: &DatabaseConnection,
    data: LedgerRecordCreate,
    user_id: &str,
) -> Result<String, AppError> {
    dao::ledger::add(db, data, user_id).await
}

/// 查询单条记账记录(仅本人可见)
pub async fn get(
    db: &DatabaseConnection,
    record_id: &str,
    user_id: &str,
) -> Result<Option<ledger_record::Model>, AppError> {
    let result = dao::ledger::get(db, record_id).await?;
    Ok(result.filter(|r| r.user_id == user_id))
}

/// 更新本人记账记录
pub async fn update(
    db: &DatabaseConnection,
    record_id: &str,
    data: LedgerRecordUpdate,
    user_id: &str,
) -> Result<(), AppError> {
    dao::ledger::update(db, record_id, data, user_id).await
}

/// 删除本人记账记录
pub async fn delete(
    db: &DatabaseConnection,
    record_id: &str,
    user_id: &str,
) -> Result<(), AppError> {
    dao::ledger::delete(db, record_id, user_id).await
}

/// 分页获取本人记账记录列表
pub async fn list_mine(
    db: &DatabaseConnection,
    pagination: &PaginationParams,
    user_id: &str,
    month: Option<String>,
    flow_type: Option<String>,
    category: Option<String>,
) -> Result<PaginationResponse<ledger_record::Model>, AppError> {
    let items = dao::ledger::list_mine(
        db,
        pagination,
        user_id,
        month.as_deref(),
        flow_type.as_deref(),
        category.as_deref(),
    )
    .await?;
    let total = dao::ledger::count_mine(
        db,
        user_id,
        month.as_deref(),
        flow_type.as_deref(),
        category.as_deref(),
    )
    .await?;
    Ok(PaginationResponse::create(items, total, pagination))
}

/// 记账统计(周期概览 + 支出分类饼图 + 趋势)
///
/// :param month: 统计周期 YYYY-MM(月度, 近6月趋势) 或 YYYY(年度, 全年12月趋势)
pub async fn stats(db: &DatabaseConnection, user_id: &str, month: String) -> Result<LedgerStats, AppError> {
    // 解析统计周期: 年度(全年12月趋势) / 月度(近6月趋势)
    let (period_start, period_end, trend_start, trend_months) = if month.len() == 4 {
        let year: i32 = month.parse().unwrap_or_default();
        let ps = NaiveDate::from_ymd_opt(year, 1, 1).expect("年度起点合法");
        let pe = NaiveDate::from_ymd_opt(year + 1, 1, 1).expect("年度终点合法");
        (ps, pe, ps, 12)
    } else {
        let year: i32 = month[..4].parse().unwrap_or_default();
        let mon: u32 = month[5..7].parse().unwrap_or_default();
        let ps = NaiveDate::from_ymd_opt(year, mon, 1).expect("月度起点合法");
        // 下月第一天(不含) — 12月跨界回绕到次年1月
        let pe = if mon == 12 {
            NaiveDate::from_ymd_opt(year + 1, 1, 1).expect("次年1月合法")
        } else {
            NaiveDate::from_ymd_opt(year, mon + 1, 1).expect("下月合法")
        };
        // 趋势起点: 当月往前推5个月(共6个月); 月份回绕用 12 取模处理
        let (ty, tm) = if mon as i32 - 5 <= 0 {
            (year - 1, mon as i32 + 7)
        } else {
            (year, mon as i32 - 5)
        };
        let ts = NaiveDate::from_ymd_opt(ty, tm as u32, 1).expect("趋势起点合法");
        (ps, pe, ts, 6)
    };

    // 周期内收/支合计
    let flows = dao::ledger::sum_by_flow(db, user_id, period_start, period_end).await?;
    let mut income_total = 0.0f64;
    let mut expense_total = 0.0f64;
    for (flow, total) in flows {
        match flow.as_str() {
            "income" => income_total = total.unwrap_or(0.0),
            _ => expense_total = total.unwrap_or(0.0),
        }
    }

    // 周期内支出分类饼图
    let pie_rows = dao::ledger::category_pie(db, user_id, period_start, period_end).await?;
    let category_pie: Vec<CategoryStat> = pie_rows
        .into_iter()
        .map(|(cat, total, count)| CategoryStat {
            category: cat,
            total: round2(total.unwrap_or(0.0)),
            count,
        })
        .collect();

    // 趋势(月度近6月 / 年度全年12月, 缺失月份补零)
    let trend_rows = dao::ledger::monthly_trend(db, user_id, trend_start, period_end).await?;
    let mut trend_map: HashMap<String, MonthTrend> = HashMap::new();
    for (m, flow, total) in trend_rows {
        let item = trend_map
            .entry(m)
            .or_insert_with(|| MonthTrend { month: String::new(), income: 0.0, expense: 0.0 });
        match flow.as_str() {
            "income" => item.income = round2(total.unwrap_or(0.0)),
            _ => item.expense = round2(total.unwrap_or(0.0)),
        }
    }
    // 按趋势区间逐月补零输出
    let mut trend: Vec<MonthTrend> = Vec::with_capacity(trend_months);
    let (mut y, mut mth) = (trend_start.year(), trend_start.month());
    for _ in 0..trend_months {
        let key = format!("{y:04}-{mth:02}");
        let mut item = trend_map.remove(&key).unwrap_or(MonthTrend {
            month: key.clone(),
            income: 0.0,
            expense: 0.0,
        });
        item.month = key;
        trend.push(item);
        mth += 1;
        if mth > 12 {
            mth = 1;
            y += 1;
        }
    }

    Ok(LedgerStats {
        month,
        income_total: round2(income_total),
        expense_total: round2(expense_total),
        balance: round2(income_total - expense_total),
        category_pie,
        trend,
    })
}
