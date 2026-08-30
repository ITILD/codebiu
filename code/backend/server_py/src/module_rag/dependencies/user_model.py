from fastapi import Depends
from module_rag.dao.user_model import UserModelDao
from module_rag.service.user_model import UserModelService
from module_ai.service.llm_base import LLMBaseService
from module_ai.dependencies.llm_base import get_llm_base_service



async def get_user_model_dao():
    """DAO工厂"""
    return UserModelDao()


async def get_user_model_service(
    dao: UserModelDao = Depends(get_user_model_dao),
    llm_base_service: LLMBaseService = Depends(get_llm_base_service),
):
    """Service工厂"""
    return UserModelService(dao,llm_base_service)
