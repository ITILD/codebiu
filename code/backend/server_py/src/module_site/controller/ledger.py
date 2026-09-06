from module_site.config.server import module_app
from module_site.dependencies.ledger import get_ledger_service
from module_site.service.ledger import LedgerService
from module_site.do.ledger import (
    LedgerRecord,
    LedgerRecordCreate,
    LedgerRecordUpdate,
    LedgerStats,
)
from module_authorization.dependencies.permission import require_permission
from common.utils.db.schema.pagination import PaginationParams, PaginationResponse

from fastapi import APIRouter, status, Depends, Query
from common.utils.fastapiEX.exceptions import NotFoundError

router = APIRouter()


@router.post(
    "", summary="记一笔(收入/支出)", status_code=status.HTTP_201_CREATED, response_model=str
)
async def create_ledger_record(
    record: LedgerRecordCreate,
    current_user_id: str = Depends(require_permission("site", "ledger", "create")),
    service: LedgerService = Depends(get_ledger_service),
) -> str:
    """
    新增记账记录
    :param record: 记账数据(金额/方向/分类/日期/备注)
    :return: 创建的记录ID
    """
    return await service.add(record, current_user_id)


@router.get("/stats", summary="记账统计(概览+饼图+趋势, 支持月/年)", response_model=LedgerStats)
async def get_ledger_stats(
    month: str = Query(
        ...,
        pattern=r"^\d{4}(-(0[1-9]|1[0-2]))?$",
        description="统计周期 YYYY-MM(月度) 或 YYYY(年度)",
    ),
    current_user_id: str = Depends(require_permission("site", "ledger", "read")),
    service: LedgerService = Depends(get_ledger_service),
) -> LedgerStats:
    """
    记账统计:
    - income_total/expense_total/balance: 周期内收支结余概览
    - category_pie: 周期内支出分类占比(饼图)
    - trend: 收支趋势(月度近6个月 / 年度全年12个月, 柱状图)
    """
    return await service.stats(current_user_id, month)


@router.get("/list", summary="分页查询记账记录", response_model=PaginationResponse)
async def list_ledger_records(
    pagination: PaginationParams = Depends(),
    month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$", description="按月过滤 YYYY-MM"),
    flow_type: str | None = Query(None, description="收支方向过滤(income/expense)"),
    category: str | None = Query(None, max_length=50, description="分类模糊搜索"),
    current_user_id: str = Depends(require_permission("site", "ledger", "read")),
    service: LedgerService = Depends(get_ledger_service),
) -> PaginationResponse:
    """
    分页查询本人记账记录(支持月份/方向/分类过滤, 按记账日期倒序)
    """
    return await service.list_mine(
        pagination, current_user_id, month=month, flow_type=flow_type, category=category
    )


# 低优先级路由(放在 /stats /list 之后)
@router.get("/{record_id}", summary="获取单条记账记录", response_model=LedgerRecord)
async def get_ledger_record(
    record_id: str,
    current_user_id: str = Depends(require_permission("site", "ledger", "read")),
    service: LedgerService = Depends(get_ledger_service),
) -> LedgerRecord:
    """获取记账记录详情(仅本人可见)"""
    # 记录不存在时返回 404(由全局异常处理器统一响应)
    result = await service.get(record_id, current_user_id)
    if not result:
        raise NotFoundError("记账记录不存在")
    return result


@router.delete(
    "/{record_id}", summary="删除记账记录", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_ledger_record(
    record_id: str,
    current_user_id: str = Depends(require_permission("site", "ledger", "delete")),
    service: LedgerService = Depends(get_ledger_service),
) -> None:
    """删除本人记账记录"""
    try:
        await service.delete(record_id, current_user_id)
    except ValueError as e:
        # 资源不存在或不属于当前用户 → 404
        raise NotFoundError(str(e))


@router.put(
    "/{record_id}", summary="更新记账记录", status_code=status.HTTP_204_NO_CONTENT
)
async def update_ledger_record(
    record_id: str,
    record: LedgerRecordUpdate,
    current_user_id: str = Depends(require_permission("site", "ledger", "update")),
    service: LedgerService = Depends(get_ledger_service),
) -> None:
    """更新本人记账记录(金额/方向/分类/日期/备注)"""
    try:
        await service.update(record_id, record, current_user_id)
    except ValueError as e:
        # 资源不存在或不属于当前用户 → 404
        raise NotFoundError(str(e))


module_app.include_router(router, prefix="/ledger/records", tags=["个人小站-记账"])
