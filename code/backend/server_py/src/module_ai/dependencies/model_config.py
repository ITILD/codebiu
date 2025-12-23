from fastapi import Depends

from module_ai.dao.model_config import ModelConfigDao
from module_ai.service.model_config import ModelConfigService


async def get_model_config_dao() -> ModelConfigDao:
    """DAO工厂"""
    return ModelConfigDao()


async def get_model_config_service(
    dao: ModelConfigDao = Depends(get_model_config_dao),
) -> ModelConfigService:
    """Service工厂"""
    return ModelConfigService(dao)
