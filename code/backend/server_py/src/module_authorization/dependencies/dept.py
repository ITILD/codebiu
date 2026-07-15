from fastapi import Depends

from module_authorization.dao.dept import DeptDao
from module_authorization.service.dept import DeptService


async def get_dept_dao():
    """DAO工厂"""
    return DeptDao()


async def get_dept_service(dao: DeptDao = Depends(get_dept_dao)):
    """Service工厂"""
    return DeptService(dao)
