from fastapi import Depends

from module_site.dao.todolist import TodolistDao
from module_site.service.todolist import TodolistService


async def get_todolist_dao() -> TodolistDao:
    """DAO工厂"""
    return TodolistDao()


async def get_todolist_service(
    dao: TodolistDao = Depends(get_todolist_dao),
) -> TodolistService:
    """Service工厂"""
    return TodolistService(dao)
