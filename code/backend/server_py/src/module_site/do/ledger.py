"""记账数据模型: 收支记录 + 图表统计响应"""
from uuid import uuid4
from datetime import date, datetime, timezone
from enum import Enum

from sqlalchemy import Column, Date, DateTime, Enum as SAEnum
from sqlmodel import Field, SQLModel


# 收支方向: 收入 / 支出
class LedgerFlow(str, Enum):
    Income = "income"
    Expense = "expense"


def _enum(col_cls: type[Enum], length: int) -> SAEnum:
    """VARCHAR 存储的枚举列(避免 PG 原生枚举与旧数据类型冲突)"""
    return SAEnum(
        col_cls, native_enum=False, length=length,
        values_callable=lambda e: [m.value for m in e],
    )


class LedgerRecordBase(SQLModel):
    """记账记录基础模型(不含数据库表配置)"""

    amount: float = Field(description="金额(元, 两位小数)")
    flow_type: LedgerFlow = Field(
        default=LedgerFlow.Expense, sa_type=_enum(LedgerFlow, 16), description="收支方向"
    )
    category: str = Field(max_length=50, description="分类(餐饮/交通/工资等)")
    note: str | None = Field(default=None, max_length=200, description="备注")
    occurred_at: date = Field(
        default_factory=date.today, sa_column=Column(Date), description="记账日期"
    )


class LedgerRecord(LedgerRecordBase, table=True):
    """记账记录数据库模型(对应数据库表)"""

    __tablename__ = "ledger_record"

    id: str = Field(
        default_factory=lambda: uuid4().hex,
        primary_key=True,
        index=True,
        description="唯一标识符",
    )
    user_id: str = Field(index=True, description="归属用户ID(记账本按用户隔离)")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
        description="创建时间",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            onupdate=lambda: datetime.now(timezone.utc),
            nullable=False,
        ),
        description="最后更新时间",
    )


class LedgerRecordCreate(SQLModel):
    """创建记账记录的请求模型(归属由令牌解析)"""

    amount: float = Field(description="金额(元)")
    flow_type: LedgerFlow = Field(default=LedgerFlow.Expense)
    category: str = Field(max_length=50, description="分类")
    note: str | None = Field(default=None, max_length=200)
    occurred_at: date = Field(default_factory=date.today)


class LedgerRecordUpdate(SQLModel):
    """更新记账记录的请求模型(全部可选, 仅更新传入字段)"""

    amount: float | None = Field(default=None)
    flow_type: LedgerFlow | None = Field(default=None, sa_type=_enum(LedgerFlow, 16))
    category: str | None = Field(default=None, max_length=50)
    note: str | None = Field(default=None, max_length=200)
    occurred_at: date | None = Field(default=None)


class CategoryStat(SQLModel):
    """分类统计(饼图数据项)"""

    category: str = Field(description="分类名")
    total: float = Field(description="合计金额")
    count: int = Field(description="笔数")


class MonthTrend(SQLModel):
    """月度收支趋势(柱状图数据项)"""

    month: str = Field(description="月份 YYYY-MM")
    income: float = Field(description="收入合计")
    expense: float = Field(description="支出合计")


class LedgerStats(SQLModel):
    """记账统计响应(周期概览 + 饼图 + 趋势)"""

    month: str = Field(description="统计周期 YYYY-MM(月度) 或 YYYY(年度)")
    income_total: float = Field(description="周期内收入合计")
    expense_total: float = Field(description="周期内支出合计")
    balance: float = Field(description="周期内结余(收入-支出)")
    category_pie: list[CategoryStat] = Field(default_factory=list, description="周期内支出分类占比")
    trend: list[MonthTrend] = Field(default_factory=list, description="收支趋势: 月度近6个月 / 年度全年12个月")
