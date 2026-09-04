from fastapi import Depends
from module_rag.dao.project_dept import ProjectDeptDao
from module_rag.service.project_dept import ProjectDeptService


async def get_project_dept_dao():
    """DAO工厂"""
    return ProjectDeptDao()


async def get_project_dept_service(dao: ProjectDeptDao = Depends(get_project_dept_dao)):
    """Service工厂"""
    return ProjectDeptService(dao)
