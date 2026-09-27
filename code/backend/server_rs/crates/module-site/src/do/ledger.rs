//! 记账数据对象(对齐 Python module_site/do/ledger.py)

use chrono::NaiveDate;
use serde::{Deserialize, Serialize};

/// 收支方向: 收入 / 支出
#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum LedgerFlow {
    Income,
    Expense,
}

impl LedgerFlow {
    pub fn as_str(self) -> &'static str {
        match self {
            LedgerFlow::Income => "income",
            LedgerFlow::Expense => "expense",
        }
    }
}

/// 创建记账记录请求(LedgerRecordCreate)
#[derive(Debug, Deserialize)]
pub struct LedgerRecordCreate {
    /// 金额(元, 两位小数)
    pub amount: f64,
    /// 收支方向(默认 expense)
    #[serde(default)]
    pub flow_type: Option<LedgerFlow>,
    /// 分类(餐饮/交通/工资等)
    pub category: String,
    #[serde(default)]
    pub note: Option<String>,
    /// 记账日期(默认今天)
    #[serde(default)]
    pub occurred_at: Option<NaiveDate>,
}

/// 更新记账记录请求(LedgerRecordUpdate, 全部可选仅更新传入字段)
#[derive(Debug, Default, Deserialize)]
pub struct LedgerRecordUpdate {
    #[serde(default)]
    pub amount: Option<f64>,
    #[serde(default)]
    pub flow_type: Option<LedgerFlow>,
    #[serde(default)]
    pub category: Option<String>,
    /// 备注(可空: 传 null 置 NULL)
    #[serde(default)]
    pub note: Option<Option<String>>,
    #[serde(default)]
    pub occurred_at: Option<NaiveDate>,
}

// ############################# 记账统计响应 #############################

/// 分类统计(饼图数据项)
#[derive(Debug, Serialize)]
pub struct CategoryStat {
    /// 分类名
    pub category: String,
    /// 合计金额
    pub total: f64,
    /// 笔数
    pub count: i64,
}

/// 月度收支趋势(柱状图数据项)
#[derive(Debug, Serialize)]
pub struct MonthTrend {
    /// 月份 YYYY-MM
    pub month: String,
    /// 收入合计
    pub income: f64,
    /// 支出合计
    pub expense: f64,
}

/// 记账统计响应(周期概览 + 饼图 + 趋势)
#[derive(Debug, Serialize)]
pub struct LedgerStats {
    /// 统计周期 YYYY-MM(月度) 或 YYYY(年度)
    pub month: String,
    /// 周期内收入合计
    pub income_total: f64,
    /// 周期内支出合计
    pub expense_total: f64,
    /// 周期内结余(收入-支出)
    pub balance: f64,
    /// 周期内支出分类占比(饼图)
    pub category_pie: Vec<CategoryStat>,
    /// 收支趋势: 月度近6个月 / 年度全年12个月
    pub trend: Vec<MonthTrend>,
}
