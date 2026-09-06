from datetime import date

from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_site.do.ledger import (
    CategoryStat,
    LedgerFlow,
    LedgerRecord,
    LedgerRecordCreate,
    LedgerRecordUpdate,
    LedgerStats,
    MonthTrend,
)
from module_site.dao.ledger import LedgerRecordDao


class LedgerService:
    """记账服务: 收支记录管理 + 月度统计(概览/饼图/趋势)"""

    def __init__(self, ledger_dao: LedgerRecordDao):
        """依赖注入构造器: 初始化所需的数据访问对象"""
        self.ledger_dao = ledger_dao

    async def add(self, record: LedgerRecordCreate, user_id: str) -> str:
        """新增记账记录(归属当前用户)
        :return: 新建记录ID
        """
        return await self.ledger_dao.add(record, user_id)

    async def get(self, record_id: str, user_id: str) -> LedgerRecord | None:
        """查询单条记账记录(仅本人可见)"""
        result = await self.ledger_dao.get(record_id)
        if result and result.user_id != user_id:
            return None
        return result

    async def update(self, record_id: str, record: LedgerRecordUpdate, user_id: str) -> None:
        """更新本人记账记录"""
        await self.ledger_dao.update(record_id, record, user_id)

    async def delete(self, record_id: str, user_id: str) -> None:
        """删除本人记账记录"""
        await self.ledger_dao.delete(record_id, user_id)

    async def list_mine(
        self,
        pagination: PaginationParams,
        user_id: str,
        month: str | None = None,
        flow_type: str | None = None,
        category: str | None = None,
    ) -> PaginationResponse:
        """分页获取本人记账记录列表"""
        items = await self.ledger_dao.list_mine(
            pagination, user_id, month=month, flow_type=flow_type, category=category
        )
        total = await self.ledger_dao.count_mine(
            user_id, month=month, flow_type=flow_type, category=category
        )
        return PaginationResponse.create(items, total, pagination)

    async def stats(self, user_id: str, month: str) -> LedgerStats:
        """记账统计(周期概览 + 支出分类饼图 + 趋势)
        :param month: 统计周期 YYYY-MM(月度, 近6月趋势) 或 YYYY(年度, 全年12月趋势)
        """
        if len(month) == 4:
            # 年度统计: 全年范围 + 全年12个月趋势
            year = int(month)
            period_start = date(year, 1, 1)
            period_end = date(year + 1, 1, 1)
            trend_start, trend_months = period_start, 12
        else:
            year, mon = int(month[:4]), int(month[5:7])
            period_start = date(year, mon, 1)
            # 下月第一天(不含) — 12月跨界回绕到次年1月
            period_end = date(year + 1, 1, 1) if mon == 12 else date(year, mon + 1, 1)
            # 趋势起点: 当月往前推5个月(共6个月); 月份回绕用 12 取模处理
            trend_year, trend_mon = year, mon - 5
            if trend_mon <= 0:
                trend_mon += 12
                trend_year -= 1
            trend_start = date(trend_year, trend_mon, 1)
            trend_months = 6

        # 周期内收/支合计
        flows = await self.ledger_dao.sum_by_flow(user_id, period_start, period_end)
        income_total = round(flows.get(LedgerFlow.Income.value, 0.0), 2)
        expense_total = round(flows.get(LedgerFlow.Expense.value, 0.0), 2)

        # 周期内支出分类饼图
        pie_rows = await self.ledger_dao.category_pie(user_id, period_start, period_end)
        category_pie = [
            CategoryStat(category=cat, total=round(total, 2), count=count)
            for cat, total, count in pie_rows
        ]

        # 趋势(月度近6月 / 年度全年12月, 缺失月份补零)
        trend_rows = await self.ledger_dao.monthly_trend(user_id, trend_start, period_end)
        trend_map: dict[str, MonthTrend] = {}
        for m, flow, total in trend_rows:
            item = trend_map.setdefault(m, MonthTrend(month=m, income=0.0, expense=0.0))
            if flow == LedgerFlow.Income.value:
                item.income = round(total, 2)
            else:
                item.expense = round(total, 2)
        trend: list[MonthTrend] = []
        y, mth = trend_start.year, trend_start.month
        for _ in range(trend_months):
            key = f"{y:04d}-{mth:02d}"
            trend.append(trend_map.get(key, MonthTrend(month=key, income=0.0, expense=0.0)))
            mth += 1
            if mth > 12:
                mth = 1
                y += 1

        return LedgerStats(
            month=month,
            income_total=income_total,
            expense_total=expense_total,
            balance=round(income_total - expense_total, 2),
            category_pie=category_pie,
            trend=trend,
        )
