from fastapi import Depends
from module_authorization.dao.token import TokenDao
from module_authorization.service.token import TokenService


async def get_token_dao():
    """TokenDao工厂函数"""
    return TokenDao()


async def get_token_service(token_dao = Depends(get_token_dao)):
    """TokenService工厂函数"""
    return TokenService(token_dao)