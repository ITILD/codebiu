from fastapi import Depends

from module_authorization.dao.user import UserDao
from module_authorization.service.user import UserService


async def get_user_dao():
    """DAO工厂"""
    return UserDao()


async def get_user_service(dao: UserDao = Depends(get_user_dao)):
    """Service工厂"""
    return UserService(dao)