from fastapi import Depends
from module_rag.dao.project_member import ProjectMemberDao
from module_rag.service.project_member import ProjectMemberService


async def get_project_member_dao():
    """DAO工厂"""
    return ProjectMemberDao()


async def get_project_member_service(dao: ProjectMemberDao = Depends(get_project_member_dao)):
    """Service工厂"""
    return ProjectMemberService(dao)
