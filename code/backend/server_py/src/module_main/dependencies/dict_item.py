from fastapi import Depends

from module_main.dao.dict_item import DictItemDao
from module_main.service.dict_item import DictItemService


async def get_dict_item_dao() -> DictItemDao:
    """字典项DAO工厂"""
    return DictItemDao()


async def get_dict_item_service(dao: DictItemDao = Depends(get_dict_item_dao)) -> DictItemService:
    """字典项Service工厂"""
    return DictItemService(dao)