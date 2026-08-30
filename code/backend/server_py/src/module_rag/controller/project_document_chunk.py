from fastapi import (
    APIRouter,
    HTTPException,
    status,
    Depends,
    UploadFile,
    File,
    Form,
)
from module_rag.config.server import module_app
from module_rag.do.project_document_chunk import SearchRequest,ProjectDocumentChunkSearchResponse
from module_authorization.dependencies.auth import get_current_user_id
from module_rag.dependencies.project_document_chunk import get_project_document_chunk_service
from module_rag.service.project_document_chunk import ProjectDocumentChunkService
router = APIRouter()

@router.post(
    "/chunks_by_question",
    response_model=list[ProjectDocumentChunkSearchResponse],  # 如果有定义，请取消注释
    summary="检索项目相似文档块",
)
async def chunks_by_question(
    request: SearchRequest,
    # 【关键】自动从 Token 中解析当前登录用户的 ID，无需前端手动传
    user_id: str = Depends(get_current_user_id),
    project_document_chunk_service: ProjectDocumentChunkService = Depends(get_project_document_chunk_service),
) -> list[ProjectDocumentChunkSearchResponse]:
    """
    根据文本内容在指定项目中检索最相关的文档块 (逻辑内联版)
    """
    try:
        results:list[ProjectDocumentChunkSearchResponse] = await project_document_chunk_service.search(request, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return results


# 注册路由
module_app.include_router(router, prefix="/project-document-chunk", tags=["项目文档块量管理"])
