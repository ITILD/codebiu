from fastapi import Depends

from module_ai.dependencies.llm_base import get_llm_base_service
from module_ai.service.data_clean import DataCleanService
from module_ai.service.llm_base import LLMBaseService


async def get_data_clean_service(
    llm_base_service: LLMBaseService = Depends(get_llm_base_service),
) -> DataCleanService:
    """获取数据清洗服务(复用 LLM 基础服务注入)"""
    return DataCleanService(llm_base_service)
