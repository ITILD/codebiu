from fastapi import Depends

from module_main.dao.dict_item import DictItemDao
from module_main.dao.dict_type import DictTypeDao
from module_main.service.dict_item import DictItemService


async def get_dict_item_dao() -> DictItemDao:
    """字典项DAO工厂"""
    return DictItemDao()


async def get_dict_type_dao() -> DictTypeDao:
    """字典类型DAO工厂"""
    return DictTypeDao()


async def get_dict_item_service(
    dao: DictItemDao = Depends(get_dict_item_dao),
    type_dao: DictTypeDao = Depends(get_dict_type_dao),
) -> DictItemService:
    """字典项Service工厂(注入字典项DAO与字典类型DAO)"""
    return DictItemService(dao, type_dao)