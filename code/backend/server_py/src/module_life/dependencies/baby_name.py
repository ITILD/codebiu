from fastapi import Depends

from module_ai.service.llm_base import LLMBaseService
from module_ai.dependencies.llm_base import get_llm_base_service
from module_life.dao.baby_name import BabyNameDao
from module_life.service.baby_name import BabyNameService


async def get_baby_name_dao() -> BabyNameDao:
    """DAO工厂"""
    return BabyNameDao()


async def get_baby_name_service(
    dao: BabyNameDao = Depends(get_baby_name_dao),
    llm_base_service: LLMBaseService = Depends(get_llm_base_service),
) -> BabyNameService:
    """Service工厂"""
    return BabyNameService(dao, llm_base_service)
