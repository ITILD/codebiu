from datetime import date

from sqlalchemy import func
from sqlmodel import Session  # noqa: F401
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, update
from common.utils.db.schema.pagination import PaginationParams
from common.config.db import DaoRel
from module_site.do.ledger import LedgerFlow, LedgerRecord, LedgerRecordCreate, LedgerRecordUpdate


class LedgerRecordDao:
    """记账记录数据访问(全部按 user_id 归属隔离)"""

    @DaoRel
    async def add(
        self, record: LedgerRecordCreate, user_id: str, session: AsyncSession | None = None
    ) -> str:
        """新增记账记录
        :param record: 记账数据
        :param user_id: 归属用户ID
        :return: 新创建记录ID
        """
        db_record = LedgerRecord.model_validate(
            record.model_dump(exclude_unset=True), update={"user_id": user_id}
        )
        session.add(db_record)
        await session.flush()
        return db_record.id

    @DaoRel
    async def get(
        self, record_id: str, session: AsyncSession | None = None
    ) -> LedgerRecord | None:
        """查询单条记录"""
        return await session.get(LedgerRecord, record_id)

    @DaoRel
    async def update(
        self,
        record_id: str,
        record: LedgerRecordUpdate,
        user_id: str,
        session: AsyncSession | None = None,
    ) -> str:
        """直接更新本人记账记录
        :raises: ValueError 记录不存在或不属于当前用户
        """
        update_data = record.model_dump(exclude_unset=True)
        stmt = (
            update(LedgerRecord)
            .where(LedgerRecord.id == record_id, LedgerRecord.user_id == user_id)
            .values(**update_data)
        )
        result = await session.exec(stmt)
        if result.rowcount == 0:
            raise ValueError(f"未找到ID为 {record_id} 的记账记录")
        await session.flush()

    @DaoRel
    async def delete(
        self, record_id: str, user_id: str, session: AsyncSession | None = None
    ) -> None:
        """删除本人记账记录
        :raises: ValueError 记录不存在或不属于当前用户
        """
        record = await session.get(LedgerRecord, record_id)
        if not record or record.user_id != user_id:
            raise ValueError(f"未找到ID为 {record_id} 的记账记录")
        await session.delete(record)
        await session.flush()

    @DaoRel
    async def list_mine(
        self,
        pagination: PaginationParams,
        user_id: str,
        session: AsyncSession | None = None,
        month: str | None = None,
        flow_type: str | None = None,
        category: str | None = None,
    ) -> list[LedgerRecord]:
        """分页查询本人记账记录(支持月份/方向/分类过滤)
        :param month: 月份 YYYY-MM
        """
        conditions = [LedgerRecord.user_id == user_id]
        if month:
            # to_char 按月匹配(occurred_at 为 Date 列)
            conditions.append(
                func.to_char(LedgerRecord.occurred_at, "YYYY-MM") == month
            )
        if flow_type:
            conditions.append(LedgerRecord.flow_type == flow_type)
        if category:
            conditions.append(LedgerRecord.category.contains(category))

        statement = (
            select(LedgerRecord)
            .where(*conditions)
            .order_by(LedgerRecord.occurred_at.desc(), LedgerRecord.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def count_mine(
        self,
        user_id: str,
        session: AsyncSession | None = None,
        month: str | None = None,
        flow_type: str | None = None,
        category: str | None = None,
    ) -> int:
        """统计本人记账总数(与列表过滤条件一致)"""
        conditions = [LedgerRecord.user_id == user_id]
        if month:
            conditions.append(
                func.to_char(LedgerRecord.occurred_at, "YYYY-MM") == month
            )
        if flow_type:
            conditions.append(LedgerRecord.flow_type == flow_type)
        if category:
            conditions.append(LedgerRecord.category.contains(category))
        statement = select(func.count()).select_from(LedgerRecord).where(*conditions)
        result = await session.exec(statement)
        return result.one()

    @DaoRel
    async def sum_by_flow(
        self, user_id: str, month_start: date, next_month_start: date,
        session: AsyncSession | None = None,
    ) -> dict[str, float]:
        """当月收/支合计: {flow_type: total}
        :param month_start: 当月第一天
        :param next_month_start: 下月第一天(不含)
        """
        statement = select(
            LedgerRecord.flow_type,
            func.coalesce(func.sum(LedgerRecord.amount), 0.0),
        ).where(
            LedgerRecord.user_id == user_id,
            LedgerRecord.occurred_at >= month_start,
            LedgerRecord.occurred_at < next_month_start,
        ).group_by(LedgerRecord.flow_type)
        result = await session.exec(statement)
        # row[0] 为枚举成员, 统一转 value 字符串作为键
        return {row[0].value: float(row[1]) for row in result.all()}

    @DaoRel
    async def category_pie(
        self, user_id: str, month_start: date, next_month_start: date,
        session: AsyncSession | None = None,
    ) -> list[tuple[str, float, int]]:
        """当月支出分类统计(饼图): [(category, total, count), ...] 按金额降序"""
        statement = (
            select(
                LedgerRecord.category,
                func.sum(LedgerRecord.amount),
                func.count(),
            )
            .where(
                LedgerRecord.user_id == user_id,
                LedgerRecord.flow_type == LedgerFlow.Expense,
                LedgerRecord.occurred_at >= month_start,
                LedgerRecord.occurred_at < next_month_start,
            )
            .group_by(LedgerRecord.category)
            .order_by(func.sum(LedgerRecord.amount).desc())
        )
        result = await session.exec(statement)
        return [(row[0], float(row[1]), int(row[2])) for row in result.all()]

    @DaoRel
    async def monthly_trend(
        self, user_id: str, trend_start: date, next_month_start: date,
        session: AsyncSession | None = None,
    ) -> list[tuple[str, str, float]]:
        """近N月收支趋势(柱状图): [(month, flow_type, total), ...]

        注: GROUP BY 中不能使用参数化表达式(PG 要求 GROUP BY 与 SELECT
        表达式完全一致), 此处改用原生 SQL + 位置序号分组
        """
        from sqlalchemy import text

        stmt = text(
            "SELECT to_char(occurred_at, 'YYYY-MM') AS month, flow_type, SUM(amount) AS total "
            "FROM ledger_record "
            "WHERE user_id = :user_id AND occurred_at >= :start AND occurred_at < :end "
            "GROUP BY 1, 2 ORDER BY 1"
        )
        result = await session.execute(
            stmt,
            {"user_id": user_id, "start": trend_start, "end": next_month_start},
        )
        return [(row[0], row[1], float(row[2])) for row in result.all()]
