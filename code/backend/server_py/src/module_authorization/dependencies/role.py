from fastapi import Depends

from module_authorization.dao.role import RoleDao
from module_authorization.service.role import RoleService


async def get_role_dao():
    """DAO工厂"""
    return RoleDao()


async def get_role_service(dao: RoleDao = Depends(get_role_dao)):
    """Service工厂"""
    return RoleService(dao)