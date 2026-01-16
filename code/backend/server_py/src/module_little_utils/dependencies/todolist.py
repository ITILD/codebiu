from fastapi import Depends

from module_little_utils.dao.todolist import TodolistDao
from module_little_utils.service.todolist import TodolistService

async def get_todolist_dao() -> TodolistDao:
    """DAO工厂"""
    return TodolistDao()
# 新增的依赖项工厂函数
async def get_todolist_service(dao: TodolistDao = Depends(get_todolist_dao)) -> TodolistService:
    """Service工厂"""
    return TodolistService(dao)
