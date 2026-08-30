from fastapi import Depends
from module_rag.dao.project_document import ProjectDocumentDao
from module_rag.service.project_document import ProjectDocumentService
from module_rag.dependencies.project import get_project_dao
from module_rag.dependencies.user_model import get_user_model_service
from module_ai.dependencies.llm_base import get_llm_base_service
from module_ai.dependencies.model_config import get_model_config_service
from module_office.dependencies.document_parse import get_document_parse_service
from module_office.dependencies.document_chunk import get_document_chunk_service
from module_rag.dependencies.project_document_chunk import get_project_document_chunk_service
async def get_project_document_dao():
    """DAO工厂"""
    return ProjectDocumentDao()


async def get_project_document_service(
    document_dao = Depends(get_project_document_dao),
    project_dao = Depends(get_project_dao),
    user_model_service = Depends(get_user_model_service),
    llm_base_service=Depends(get_llm_base_service),
    model_config_service=Depends(get_model_config_service),
    document_parse_service=Depends(get_document_parse_service),
    document_chunk_service=Depends(get_document_chunk_service),
    project_document_chunk_service=Depends(get_project_document_chunk_service),
):
    """Service工厂"""
    return ProjectDocumentService(
        document_dao,
        project_dao,
        user_model_service,
        llm_base_service,
        model_config_service,
        document_parse_service,
        document_chunk_service,
        project_document_chunk_service
    )
