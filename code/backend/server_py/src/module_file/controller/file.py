from module_file.config.server import module_app
from module_file.dependencies.file import get_file_service
from module_file.service.file import FileService
from module_file.do.file import File, FileCreate, FileUpdate
from common.utils.db.schema.pagination import (
    InfiniteScrollParams,
    InfiniteScrollResponse,
    PaginationParams,
    PaginationResponse,
)

from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File as FastAPIFile
from fastapi.responses import StreamingResponse
import io

router = APIRouter()

@router.post(
    "/upload", summary="上传文件", status_code=status.HTTP_201_CREATED, response_model=File
)
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    description: str = None,
    uploaded_by: str = None,
    service: FileService = Depends(get_file_service)
) -> File:
    """
    上传文件
    :param file: 要上传的文件
    :param description: 文件描述
    :param uploaded_by: 上传者ID
    :param service: 文件服务依赖注入
    :return: 上传的文件信息
    """
    try:
        return await service.upload_file(file, description, uploaded_by)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

@router.get(
    "/download/{file_id}", summary="下载文件"
)
async def download_file(
    file_id: str,
    service: FileService = Depends(get_file_service)
):
    """
    下载文件
    :param file_id: 文件ID
    :param service: 文件服务依赖注入
    :return: 文件数据流
    """
    try:
        file_name, mime_type, content = await service.download_file(file_id)
        
        # 返回文件流
        return StreamingResponse(
            io.BytesIO(content),
            media_type=mime_type,
            headers={
                "Content-Disposition": f'attachment; filename="{file_name}"'
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

@router.get("/scroll", summary="滚动加载文件列表")
async def infinite_scroll(
    params: InfiniteScrollParams = Depends(),
    service: FileService = Depends(get_file_service),
)-> InfiniteScrollResponse:
    """
    无限滚动接口实现
    :param params: 分页参数
    :param service: 服务层依赖
    :return: 分页响应数据
    """
    try:
        infinite_scroll_response = await service.get_scroll(params)
        return infinite_scroll_response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

@router.get("/list", summary="分页查询文件列表", response_model=PaginationResponse)
async def list_files(
    pagination: PaginationParams = Depends(),
    service: FileService = Depends(get_file_service),
) -> PaginationResponse:
    """
    分页查询文件列表
    :param pagination: 分页参数 (通过查询参数传递)
    :param service: 文件服务依赖注入
    :return: 分页响应结果
    """
    try:
        pagination_response: PaginationResponse = await service.list_all(pagination)
        return pagination_response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

@router.get("/{file_id}", summary="获取文件信息", response_model=File)
async def get_file(
    file_id: str,
    service: FileService = Depends(get_file_service),
) -> File:
    """
    获取单个文件详情
    :param file_id: 文件ID
    :param service: 文件服务依赖注入
    :return: 文件详情
    """
    try:
        result = await service.get(file_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在"
            )
        return result
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

@router.delete("/{file_id}", summary="删除文件", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: str,
    service: FileService = Depends(get_file_service),
):
    """
    删除文件（同时删除物理文件和数据库记录）
    :param file_id: 文件ID
    :param service: 文件服务依赖注入
    """
    try:
        await service.delete(file_id)
    except Exception as e:
        if "未找到" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

@router.put("/{file_id}", summary="更新文件信息", response_model=File)
async def update_file(
    file_id: str,
    file_update: FileUpdate,
    service: FileService = Depends(get_file_service),
) -> File:
    """
    更新文件信息
    :param file_id: 文件ID
    :param file_update: 更新数据
    :param service: 文件服务依赖注入
    :return: 更新后的文件信息
    """
    try:
        # 先检查文件是否存在
        existing_file = await service.get(file_id)
        if not existing_file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在"
            )
        
        # 更新文件信息
        await service.update(file_id, file_update)
        
        # 返回更新后的文件信息
        return await service.get(file_id)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

# 将路由注册到模块应用
module_app.include_router(router, prefix="", tags=["文件管理"])