from fastapi import Depends

from module_ai.dependencies.llm import get_llm_service
from module_ai.service.llm import LLMService
from module_data_clean.service.data_clean import DataCleanService


async def get_data_clean_service(
    llm_service: LLMService = Depends(get_llm_service),
) -> DataCleanService:
    """获取数据清洗服务(复用 module_ai 的 LLM 基础服务注入)"""
    return DataCleanService(llm_service)
