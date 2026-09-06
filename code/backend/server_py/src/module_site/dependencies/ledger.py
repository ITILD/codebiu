from fastapi import Depends

from module_site.dao.ledger import LedgerRecordDao
from module_site.service.ledger import LedgerService


async def get_ledger_dao() -> LedgerRecordDao:
    """DAO工厂"""
    return LedgerRecordDao()


async def get_ledger_service(
    dao: LedgerRecordDao = Depends(get_ledger_dao),
) -> LedgerService:
    """Service工厂"""
    return LedgerService(dao)
