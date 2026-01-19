from fastapi import Depends

from module_main.dao.dict_type import DictTypeDao
from module_main.service.dict_type import DictTypeService


async def get_dict_type_dao() -> DictTypeDao:
    """字典类型DAO工厂"""
    return DictTypeDao()


async def get_dict_type_service(dao: DictTypeDao = Depends(get_dict_type_dao)) -> DictTypeService:
    """字典类型Service工厂"""
    return DictTypeService(dao)