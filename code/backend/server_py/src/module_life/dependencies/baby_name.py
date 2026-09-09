from fastapi import Depends

from module_ai.service.llm import LLMService
from module_ai.dependencies.llm import get_llm_service
from module_life.dao.baby_name import BabyNameDao
from module_life.service.baby_name import BabyNameService


async def get_baby_name_dao() -> BabyNameDao:
    """DAO工厂"""
    return BabyNameDao()


async def get_baby_name_service(
    dao: BabyNameDao = Depends(get_baby_name_dao),
    llm_service: LLMService = Depends(get_llm_service),
) -> BabyNameService:
    """Service工厂"""
    return BabyNameService(dao, llm_service)
