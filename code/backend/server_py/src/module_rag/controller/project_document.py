from fastapi import (
    APIRouter,
    HTTPException,
    status,
    Depends,
    UploadFile,
    File,
    Form,
)
from fastapi.responses import StreamingResponse
from pathlib import Path

from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_rag.do.project_document import (
    ProjectDocument,
    ProjectDocumentUpdate,
    ProjectDocumentResponse,
)
from module_rag.service.project_document import ProjectDocumentService
from module_rag.dependencies.project_document import get_project_document_service
from module_authorization.dependencies.auth import get_current_user_id
from module_authorization.dependencies.permission import (
    enforce_project_permission,
    require_project_permission,
)
from module_rag.config.server import module_app
# 确保导入你修改后的 DocType
from module_rag.do.project_document import DocType 
from module_file.utils.base.file_utils import FileUtils
from module_rag.tasks.project_document import reparse_document_task

router = APIRouter()


@router.post(
    "/{project_id}/upload",
    summary="上传文档到项目",
    status_code=status.HTTP_201_CREATED,
    response_model=ProjectDocumentResponse,
)
async def upload_project_document(
    project_id: str,
    file: UploadFile,
    description: str | None = Form(default=None),
    current_user_id: str = Depends(require_project_permission("doc", "upload")),
    service: ProjectDocumentService = Depends(get_project_document_service),
) -> ProjectDocumentResponse:
    """
    上传文档到指定项目(保存至 DIR_UPLOAD/{project_id}/{uuid_filename})
    :param project_id: 项目ID(作为文件夹名)
    :param file: 上传的文件(支持 pdf/docx/xlsx/pptx 等常见文档格式)
    :param description: 文档描述
    :param current_user_id: 当前登录用户ID(由 token 自动解析)
    :param service: 文档服务依赖注入
    :return: 文档元数据
    """
    try:
        document = await service.upload_document(
            project_id, file, current_user_id, description
        )
        return ProjectDocumentResponse.model_validate(document.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/{project_id}/list",
    summary="分页查询项目文档列表",
    response_model=PaginationResponse,
)
async def list_project_documents(
    project_id: str,
    pagination: PaginationParams = Depends(),
    current_user_id: str = Depends(require_project_permission("doc", "read")),
    service: ProjectDocumentService = Depends(get_project_document_service),
) -> PaginationResponse:
    """
    分页查询项目文档列表
    :param project_id: 项目ID
    :param pagination: 分页参数
    :param service: 文档服务依赖注入
    :return: 分页文档列表
    """
    try:
        return await service.list_by_project(project_id, pagination)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/{document_id}",
    summary="获取文档详情",
    response_model=ProjectDocumentResponse,
)
async def get_project_document(
    document_id: str,
    current_user_id: str = Depends(get_current_user_id),
    service: ProjectDocumentService = Depends(get_project_document_service),
) -> ProjectDocumentResponse:
    """
    获取文档元数据
    :param document_id: 文档ID
    :param current_user_id: 当前登录用户ID(由 token 自动解析)
    :param service: 文档服务依赖注入
    :return: 文档元数据
    """
    try:
        document = await service.get_document(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="文档不存在")
        # 权限校验: 通过文档解析所属项目
        await enforce_project_permission(
            current_user_id, document.project_id, "doc", "read"
        )
        return ProjectDocumentResponse.model_validate(document.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/{document_id}/download",
    summary="下载文档",
)
async def download_project_document(
    document_id: str,
    current_user_id: str = Depends(get_current_user_id),
    service: ProjectDocumentService = Depends(get_project_document_service),
):
    """
    下载文档(流式返回)
    :param document_id: 文档ID
    :param current_user_id: 当前登录用户ID(由 token 自动解析)
    :param service: 文档服务依赖注入
    :return: 文件流
    """
    try:
        # 权限校验: 通过文档解析所属项目
        document = await service.get_document(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="文档不存在")
        await enforce_project_permission(
            current_user_id, document.project_id, "doc", "read"
        )
        file_name, mime_type, file_path = await service.get_file_for_download(document_id)
        return StreamingResponse(
            FileUtils.read_file_stream(file_path),
            media_type=mime_type or "application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put(
    "/{document_id}",
    summary="更新文档信息",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def update_project_document(
    document_id: str,
    document: ProjectDocumentUpdate,
    current_user_id: str = Depends(get_current_user_id),
    service: ProjectDocumentService = Depends(get_project_document_service),
):
    """
    更新文档元数据(仅 name/description)
    :param document_id: 文档ID
    :param document: 更新数据
    :param current_user_id: 当前登录用户ID(由 token 自动解析)
    :param service: 文档服务依赖注入
    """
    try:
        # 权限校验: 通过文档解析所属项目
        doc_info = await service.get_document(document_id)
        if not doc_info:
            raise HTTPException(status_code=404, detail="文档不存在")
        await enforce_project_permission(
            current_user_id, doc_info.project_id, "doc", "update"
        )
        await service.update(document_id, document)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.delete(
    "/{document_id}",
    summary="删除文档",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_project_document(
    document_id: str,
    current_user_id: str = Depends(get_current_user_id),
    service: ProjectDocumentService = Depends(get_project_document_service),
):
    """
    删除文档(同时删除物理文件与数据库记录)
    :param document_id: 文档ID
    :param current_user_id: 当前登录用户ID(由 token 自动解析)
    :param service: 文档服务依赖注入
    """
    try:
        # 权限校验: 通过文档解析所属项目
        doc_info = await service.get_document(document_id)
        if not doc_info:
            raise HTTPException(status_code=404, detail="文档不存在")
        await enforce_project_permission(
            current_user_id, doc_info.project_id, "doc", "delete"
        )
        await service.delete_document(document_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post(
    "/{document_id}/reparse",
    summary="重新解析文档",
    response_model=bool,
)
async def reparse_project_document(
    document_id: str,
    current_user_id: str = Depends(get_current_user_id),
    service: ProjectDocumentService = Depends(get_project_document_service),
) -> bool:
    """
    重新解析文档：读取文件内容并返回是否成功
    :param document_id: 文档ID
    :param current_user_id: 当前登录用户ID(由 token 自动解析)
    :param service: 文档服务依赖注入
    :return: 是否成功
    """
    try:
        # 权限校验: 通过文档解析所属项目
        doc_info = await service.get_document(document_id)
        if not doc_info:
            raise HTTPException(status_code=404, detail="文档不存在")
        await enforce_project_permission(
            current_user_id, doc_info.project_id, "doc", "update"
        )
        # return await service.reparse_document(document_id, current_user_id)
        return await service.parse_document(document_id, current_user_id)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

@router.post(
    "/{document_id}/reparse_task",
    summary="重新解析文档加入任务队列",
    response_model=bool,
)
async def reparse_project_document_task(
    document_id: str,
    current_user_id: str = Depends(get_current_user_id),
    service: ProjectDocumentService = Depends(get_project_document_service),
) -> dict:
    """
    重新解析文档(异步任务队列版本)
    :param document_id: 文档ID
    :param current_user_id: 当前登录用户ID(由 token 自动解析)
    :param service: 文档服务依赖注入
    :return: 任务提交结果
    """
    try:
        # 权限校验: 通过文档解析所属项目
        doc_info = await service.get_document(document_id)
        if not doc_info:
            raise HTTPException(status_code=404, detail="文档不存在")
        await enforce_project_permission(
            current_user_id, doc_info.project_id, "doc", "update"
        )
        reparse_document_task.delay(document_id, current_user_id)
        return {"message": "解析任务已提交至后台队列", "document_id": document_id}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )



@router.get(
    "/supported-types", 
    summary="获取支持上传的文件格式列表",
    description="返回系统支持的所有文件格式，按文档、图片、音频、视频分类，供前端渲染上传组件使用。"
)
async def get_supported_file_types():
    """
    获取支持上传的文件格式列表
    """
    return {
        "code": 200,
        "message": "success",
        "data": {
            "documents": DocType.DOCUMENT_TYPES,
            "images": DocType.IMAGE_TYPES,
            "audios": DocType.AUDIO_TYPES,
            "videos": DocType.VIDEO_TYPES,
            "all_extensions": DocType.ALLOWED_EXTENSIONS  # 扁平列表，方便直接传给 <input accept="...">
        }
    }



# 注册路由
module_app.include_router(router, prefix="/project-documents", tags=["项目文档管理"])
