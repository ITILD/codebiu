from module_file.config.server import module_app
from module_file.dependencies.filesystem import get_file_service
from module_file.service.filesystem import FileService
from module_file.do.filesystem import (
    FileEntryCreate,
    FileEntry,
    FileEntryUpdate,
    GeneratePresignedUrlRequest,
    PresignedUploadParams,
    PresignedDownloadParams,
    GeneratePresignedUploadResponse,
    GeneratePresignedDownloadResponse,
    UploadSuccessResponse,
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
    利用SHA-256 的Preimage Resistance达到文件去重妙传和安全性保证
    (新文件要后校验hash值,因为无法确认新文件hash值与文件匹配,默认前端无准确性)
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
        response.headers["ETag"] = (
            "test_md5"  # TODO 用来校验文件是否上传成功 且防止下次重复
        )
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
        file_id = await service.presigned_url_upload_success(file)
        return UploadSuccessResponse(file_id=file_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


######################################兼容s3/minio/oss/rustfs对象存储 删除逻辑######################################
@router.delete(
    "/file/{file_id}",
    summary="逻辑删除文件,(兼容本地和s3/minio/oss/rustfs对象存储)",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_file(
    file_id: str,
    service: FileService = Depends(get_file_service),
):
    """
    删除目录或文件(同时删除数据库记录)
    :param file_id: 文件ID
    :param service: 文件服务依赖注入
    """
    try:
        await service.delete_file(file_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.delete(
    "/folder/{folder_id}",
    summary="逻辑删除目录,(兼容本地和s3/minio/oss/rustfs对象存储)",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_folder(
    folder_id: str,
    service: FileService = Depends(get_file_service),
):
    """
    删除目录(同时删除数据库记录)
    :param folder_id: 文件ID
    :param service: 文件服务依赖注入
    """
    try:
        await service.delete_folder(folder_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# TODO 真实删除  直接走后端(s3/本地)
# async def delete_file_real(
#     file_id: str,
#     service: FileService = Depends(get_file_service),
# ):
#     """
#     删除文件(同时删除数据库记录)
#     :param file_id: 文件ID
#     :param service: 文件服务依赖注入
#     """
#     try:
#         await service.delete_file_real(file_id)
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=str(e),
#         )


######################################兼容s3/minio/oss/rustfs对象存储 改文件######################################


######################################兼容s3/minio/oss/rustfs对象存储 获取文件######################################
@router.get(
    "/file_entry/{file_entry_id}",
    summary="获取文件或文件夹元数据",
    response_model=FileEntry,
    status_code=status.HTTP_200_OK,
)
async def get_file_entry_info(
    file_entry_id: str,
    service: FileService = Depends(get_file_service),
) -> FileEntry:
    """
    获取文件或文件夹元数据
    :param file_entry_id: 文件或目录的ID
    :param service: 文件服务依赖注入
    :return: 文件或文件夹元数据
    """
    try:
        result = await service.get_file_entry(file_entry_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="文件或目录不存在"
            )
        return result
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/generate_presigned_url_download/{file_id}",
    summary="生成预签名URL用于下载文件(兼容s3/minio/oss/rustfs对象存储)",
    status_code=status.HTTP_200_OK,
)
async def generate_presigned_url_download(
    file_id: str,
    request: Request,
    service: FileService = Depends(get_file_service),
) -> GeneratePresignedDownloadResponse:
    """
    生成预签名URL用于下载文件
    :param file_id: 文件ID
    :param service: 文件服务依赖注入
    :return: 预签名URL
    """
    try:
        # 获取当前url 解析位置和参数
        presigned_url_path = request.url.path.removesuffix(f"/{file_id}")
        generate_presigned_download_response = (
            await service.generate_presigned_url_download(file_id, presigned_url_path)
        )
        if generate_presigned_download_response is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文件不存在或生成预签名URL失败",
            )
        return generate_presigned_download_response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/presigned_url_download/{file_path:path}",
    summary="使用预签名URL下载文件",
    status_code=status.HTTP_200_OK,
)
async def download_with_presigned_url(
    file_path: str,
    presigned_download_params: PresignedDownloadParams = Depends(),
    service: FileService = Depends(get_file_service),
) -> Response:
    """
    使用预签名URL下载文件
    :param file_path: 文件路径
    :param presigned_download_params: 预签名下载参数
    :param service: 文件服务依赖注入
    :return: 文件内容
    """
    try:
        content = await service.presigned_url_download(
            file_path, presigned_download_params
        )
        if content is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="使用预签名URL下载失败或文件不存在",
            )
        return Response(
            content=content,
            media_type="application/octet-stream",  # 关键：强制二进制流，禁用自动序列化
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


######################################兼容s3/minio/oss/rustfs对象存储 查文件######################################

######################################兼容s3/minio/oss/rustfs对象存储 同步文件######################################
# TODO 数据同步接口

# 将路由注册到模块应用
module_app.include_router(router, prefix="/filesystem", tags=["文件管理"])
