from fastapi import Depends
from module_rag.dao.project_document_chunk import ProjectDocumentChunkDao
from module_rag.service.project_document_chunk import ProjectDocumentChunkService
from module_rag.dependencies.user_model import get_user_model_service
from module_rag.service.user_model import UserModelService

def get_project_document_chunk_dao() -> ProjectDocumentChunkDao:
    """文档分块DAO工厂(FastAPI依赖注入)"""
    return ProjectDocumentChunkDao()

def get_project_document_chunk_service(
    project_document_chunk_dao: ProjectDocumentChunkDao = Depends(get_project_document_chunk_dao),
    user_model_service: UserModelService = Depends(get_user_model_service),
) -> ProjectDocumentChunkService:
    """文档分块服务工厂(FastAPI依赖注入)"""
    return ProjectDocumentChunkService(
        project_document_chunk_dao,
        user_model_service,
    )
