from fastapi import Depends
from module_rag.dao.project import ProjectDao
from module_rag.service.project import ProjectService


async def get_project_dao():
    """DAO工厂"""
    return ProjectDao()


async def get_project_service(dao: ProjectDao = Depends(get_project_dao)):
    """Service工厂"""
    return ProjectService(dao)
