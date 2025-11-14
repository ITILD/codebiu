from fastapi import Depends

from module_authorization.dao.permission import PermissionDao
from module_authorization.service.permission import PermissionService


async def get_permission_dao():
    """DAO工厂"""
    return PermissionDao()


async def get_permission_service(dao: PermissionDao = Depends(get_permission_dao)):
    """Service工厂"""
    return PermissionService(dao)