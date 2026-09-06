from fastapi import Depends
from module_rag.dao.project import ProjectDao
from module_rag.dao.project_member import ProjectMemberDao
from module_rag.dao.project_document import ProjectDocumentDao
from module_rag.service.project import ProjectService
from module_rag.dependencies.project_member import get_project_member_dao
from module_rag.dao.project_document_chunk import ProjectDocumentChunkDao
from module_rag.dependencies.project_document_chunk import get_project_document_chunk_dao
from module_file.dependencies.filesystem import get_file_service


async def get_project_dao():
    """DAO工厂"""
    return ProjectDao()


async def get_project_document_dao_for_project():
    """ProjectDocumentDao工厂(供 ProjectService 使用)"""
    return ProjectDocumentDao()


async def get_project_service(
    project_dao: ProjectDao = Depends(get_project_dao),
    member_dao: ProjectMemberDao = Depends(get_project_member_dao),
    document_dao: ProjectDocumentDao = Depends(get_project_document_dao_for_project),
    project_document_chunk_dao: ProjectDocumentChunkDao = Depends(get_project_document_chunk_dao),
    file_service=Depends(get_file_service),
):
    """Service工厂"""
    return ProjectService(project_dao, member_dao, document_dao, project_document_chunk_dao,
                          file_service=file_service)
