from module_file.config.server import module_app
from module_file.dependencies.filesystem import get_file_service
from module_file.service.filesystem import FileService
from module_file.do.filesystem import (
    FileEntryCreate,
    FileEntry,
    FileEntryUpdate,
    GeneratePresignedUrlRequest,
    PresignedUploadParams,
    GeneratePresignedUploadResponse,
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
    Response,
)
from fastapi.responses import StreamingResponse

router = APIRouter()


@router.post(
    "/upload",
    summary="上传文件(简易)",
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


@router.get("/download/{file_content_id}", summary="下载文件(简易)")
async def download_file(
    file_content_id: str, service: FileService = Depends(get_file_service)
):
    """
    下载文件
    :param file_content_id: 文件ID
    :param service: 文件服务依赖注入
    :return: 文件数据流
    """
    try:
        file_name, mime_type, file_path = await service.get_file_info_for_download(
            file_content_id
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


@router.get("/{file_content_id}", summary="获取文件信息", response_model=FileEntry)
async def get_file(
    file_content_id: str,
    service: FileService = Depends(get_file_service),
):
    """
    获取单个文件详情
    :param file_content_id: 文件ID
    :param service: 文件服务依赖注入
    :return: 文件详情
    """
    try:
        result = await service.get(file_content_id)
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


@router.put("/{file_content_id}", summary="更新文件信息", response_model=FileEntry)
async def update_file(
    file_content_id: str,
    file_update: FileEntryUpdate,
    service: FileService = Depends(get_file_service),
) -> None:
    """
    更新文件信息
    :param file_content_id: 文件ID
    :param file_update: 更新数据
    :param service: 文件服务依赖入
    :return: 更新后的文件信息
    """
    try:
        # 更新文件信息并返回更新后的文件信息（在同一事务中）
        await service.update(file_content_id, file_update)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# 获取目录下的所有文件和子目录
# @router.get("/list_dir/{dir_path}", summary="获取目录下的所有文件和子目录", response_model=list[str])
# async def list_dir(
#     dir_path: str,
#     response_model=list[str],
# ) -> list[str]:
#     """
#     获取目录下的所有文件和子目录
#     :param dir_path: 目录路径
#     :return: 目录下的所有文件和子目录
#     """
#     try:
#         return await service.list_dir(dir_path)
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
#         )

# 获取文件统计信息

######################################兼容s3/minio/oss/rustfs对象存储######################################


@router.delete(
    "/{file_content_id}",
    summary="删除文件,(兼容本地和s3/minio/oss/rustfs对象存储)",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_file(
    file_content_id: str,
    service: FileService = Depends(get_file_service),
):
    """
    删除文件(同时删除物理文件和数据库记录)
    :param file_content_id: 文件ID
    :param service: 文件服务依赖注入
    """
    try:
        await service.delete(file_content_id)
    except Exception as e:
        if "未找到" in str(e):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


######################################兼容s3/minio/oss/rustfs对象存储 上传文件######################################
@router.post(
    "/generate_presigned_url_upload",
    summary="上传文件,生成预签名URL(兼容s3/minio/oss/rustfs对象存储)",
    status_code=status.HTTP_200_OK,
)
async def generate_presigned_url_upload(
    presigned_url_request: GeneratePresignedUrlRequest,
    request: Request,
    service: FileService = Depends(get_file_service),
) -> GeneratePresignedUploadResponse:
    """
    生成预签名URL用于上传文件
    :param request: 生成预签名URL的请求参数
    :param service: 文件服务依赖注入
    :return: 预签名URL
    """
    try:
        # 获取当前url 解析位置和参数
        presigned_url_path = request.url.path
        generate_presigned_upload_response = (
            await service.generate_presigned_url_upload(
                presigned_url_request, presigned_url_path
            )
        )
        if generate_presigned_upload_response is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="生成预签名URL失败",
            )
        return generate_presigned_upload_response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

@router.put(
    "/presigned_url_upload/{file_path:path}",
    summary="上传文件,使用预签名URL(兼容s3/minio/oss/rustfs对象存储)",
    status_code=status.HTTP_200_OK,
)
async def presigned_url_upload(
    request: Request,
    response: Response,
    file_path: str,
    presigned_upload_params: PresignedUploadParams = Depends(),
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
        # 文件头里读取类型
        content: bytes = await request.body()
        success = await service.presigned_url_upload(
            file_path, presigned_upload_params, content
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="file upload by presigned url failed",
            )
        response.headers["ETag"] = "test_md5"  # 用来校验文件是否上传成功 且防止下次重复
        return {"success": True, "message": "file upload success"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post(
    "/presigned_url_upload_success",
    summary="上传成功通知,增加信息记录(兼容s3/minio/oss/rustfs对象存储)",
    status_code=status.HTTP_200_OK,
)
async def presigned_url_upload_success(
    file: FileEntryCreate,
    service: FileService = Depends(get_file_service),
):
    """
    通知后端对象/本地存储完成,新增元数据   防止hash攻击,需要校验文件,符合s3对象存储的hash校验规则
    :param file_content_id: 文件ID
    :param service: 文件服务依赖注入
    :return: 通知结果
    """
    try:
        await service.presigned_url_upload_success(file)
        return {"success": True, "code": "FILE_UPLOAD_SUCCESS", "message": "file upload success"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

######################################兼容s3/minio/oss/rustfs对象存储 下载文件######################################
@router.get(
    "/generate_presigned_url_download",
    summary="生成预签名URL用于下载文件(兼容s3/minio/oss/rustfs对象存储)",
    status_code=status.HTTP_200_OK,
)
async def generate_presigned_url_download(
    file_content_id: str = Query(..., description="文件ID"),
    service: FileService = Depends(get_file_service),
):
    """
    生成预签名URL用于下载文件
    :param file_content_id: 文件ID
    :param service: 文件服务依赖注入
    :return: 预签名URL
    """
    try:
        presigned_url = await service.generate_presigned_url_download(file_content_id)
        if presigned_url is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文件不存在或生成预签名URL失败",
            )
        return {"presigned_url": presigned_url}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/presigned_url_download",
    summary="使用预签名URL下载文件",
    status_code=status.HTTP_200_OK,
)
async def download_with_presigned_url(
    presignfile_ided_url: str = Query(..., description="预签名URL"),
    service: FileService = Depends(get_file_service),
):
    """
    使用预签名URL下载文件
    :param presigned_url: 预签名URL
    :param service: 文件服务依赖注入
    :return: 文件内容
    """
    try:
        content = await service.generate_presigned_url_download(presignfile_ided_url)
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
        
######################################兼容s3/minio/oss/rustfs对象存储 同步文件######################################        
# TODO 数据同步接口

# 将路由注册到模块应用
module_app.include_router(router, prefix="/filesystem", tags=["文件管理"])
