from module_file.config.server import module_app
from module_file.dependencies.filesystem import get_file_service
from module_file.service.filesystem import FileService
from module_file.do.filesystem import (
    FileEntry,
    FileEntryUpdate,
    PresignedUrlRequest,
)
from common.utils.db.schema.pagination import (
    InfiniteScrollParams,
    InfiniteScrollResponse,
    PaginationParams,
    PaginationResponse,
)

from fastapi import (
    APIRouter,
    HTTPException,
    status,
    Depends,
    UploadFile,
    File as FastAPIFile,
    Query,
    Request,
)
from fastapi.responses import StreamingResponse

router = APIRouter()


@router.post(
    "/upload",
    summary="上传文件",
    status_code=status.HTTP_201_CREATED,
    response_model=FileEntry,
)
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    description: str = None,
    owner_user_id: str = None,
    service: FileService = Depends(get_file_service),
) -> FileEntry:
    """
    上传文件
    :param file: 要上传的文件
    :param description: 文件描述
    :param uploaded_by: 上传者ID TODO jwt注入
    :param service: 文件服务依赖注入
    :return: 上传的文件信息
    """
    try:
        return await service.upload_file(file, description, owner_user_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/download/{file_id}", summary="下载文件")
async def download_file(file_id: str, service: FileService = Depends(get_file_service)):
    """
    下载文件
    :param file_id: 文件ID
    :param service: 文件服务依赖注入
    :return: 文件数据流
    """
    try:
        file_name, mime_type, file_path = await service.get_file_info_for_download(
            file_id
        )

        # 返回文件流
        iter_file = service.stream_file_content(file_path)

        return StreamingResponse(
            iter_file,
            media_type=mime_type,
            headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
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
) -> InfiniteScrollResponse:
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


@router.get("/{file_id}", summary="获取文件信息", response_model=FileEntry)
async def get_file(
    file_id: str,
    service: FileService = Depends(get_file_service),
):
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
    删除文件(同时删除物理文件和数据库记录)
    :param file_id: 文件ID
    :param service: 文件服务依赖注入
    """
    try:
        await service.delete(file_id)
    except Exception as e:
        if "未找到" in str(e):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put("/{file_id}", summary="更新文件信息", response_model=FileEntry)
async def update_file(
    file_id: str,
    file_update: FileEntryUpdate,
    service: FileService = Depends(get_file_service),
) -> None:
    """
    更新文件信息
    :param file_id: 文件ID
    :param file_update: 更新数据
    :param service: 文件服务依赖入
    :return: 更新后的文件信息
    """
    try:
        # 更新文件信息并返回更新后的文件信息（在同一事务中）
        await service.update(file_id, file_update)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


generate_presigned_url_str = "/generate_presigned_url"
upload_with_presigned_url_str = "/upload_with_presigned_url"


@router.post(
    generate_presigned_url_str, summary="生成预签名URL", status_code=status.HTTP_200_OK
)
async def generate_presigned_url(
    presigned_url_request: PresignedUrlRequest,
    request: Request,
    service: FileService = Depends(get_file_service),
):
    """
    生成预签名URL
    :param request: 生成预签名URL的请求参数
    :param service: 文件服务依赖注入
    :return: 预签名URL
    """
    try:
        # 获取当前url 解析位置和参数
        presigned_url_path = request.url.path
        # 换成上传时url
        upload_url = presigned_url_path.replace(
            generate_presigned_url_str, upload_with_presigned_url_str
        )
        presigned_url = await service.generate_presigned_url(presigned_url_request)
        if presigned_url is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="生成预签名URL失败",
            )
        # 替换预签名URL中的路径为当前URL
        presigned_url = upload_url + presigned_url
        return presigned_url
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post(
    upload_with_presigned_url_str,
    summary="使用预签名URL上传文件",
    status_code=status.HTTP_200_OK,
)
async def upload_with_presigned_url(
    request: Request,
    file: UploadFile = FastAPIFile(...),
    service: FileService = Depends(get_file_service),
):
    """
    使用预签名URL上传文件
    :param presigned_url: 预签名URL
    :param file: 要上传的文件
    :param service: 文件服务依赖注入
    :return: 上传结果
    """
    try:
        # 读取预签信息
        current_url = str(request.url.path)
        content = await file.read()
        success = await service.upload_with_presigned_url(presigned_url, content)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="使用预签名URL上传失败",
            )
        return {"success": True, "message": "文件上传成功"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# 生成下载用的预签名 URL
download_with_presigned_url_str = "/download_with_presigned_url"


@router.get(
    download_with_presigned_url_str,
    summary="使用预签名URL下载文件",
    status_code=status.HTTP_200_OK,
)
async def download_with_presigned_url(
    presigned_url: str = Query(..., description="预签名URL"),
    service: FileService = Depends(get_file_service),
):
    """
    使用预签名URL下载文件
    :param presigned_url: 预签名URL
    :param service: 文件服务依赖注入
    :return: 文件内容
    """
    try:
        content = await service.download_with_presigned_url(presigned_url)
        if content is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="使用预签名URL下载失败或文件不存在",
            )
        return StreamingResponse(
            iter([content]),
            media_type="application/octet-stream",
            headers={"Content-Disposition": "attachment; filename=temp_file"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# 将路由注册到模块应用
module_app.include_router(router, prefix="/filesystem", tags=["文件管理"])
