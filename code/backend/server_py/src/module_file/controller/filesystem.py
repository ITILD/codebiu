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
    MigrateRequest,
)
from module_authorization.dependencies.auth import get_current_user_id
from module_authorization.dependencies.permission import require_permission
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

# 预签名上传/下载代理端点路径(本地存储签名拼接用,与下方路由路径保持一致)
PRESIGNED_UPLOAD_PROXY_PATH = "/filesystem/presigned/upload"
PRESIGNED_DOWNLOAD_PROXY_PATH = "/filesystem/presigned/download"


@router.post(
    "/upload",
    summary="上传文件到指定目录(内容哈希去重)",
    status_code=status.HTTP_201_CREATED,
    response_model=FileEntry,
)
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    description: str = None,
    pid: str = None,
    current_user_id: str = Depends(require_permission("main", "file", "create")),
    service: FileService = Depends(get_file_service),
) -> FileEntry:
    """
    上传文件到指定目录(虚拟文件系统)
    :param file: 要上传的文件
    :param description: 文件描述
    :param pid: 父目录ID(为空上传到根目录)
    :param current_user_id: 当前登录用户ID(权限依赖注入,文件归属者)
    :param service: 文件服务依赖注入
    :return: 上传的文件信息
    """
    try:
        return await service.upload_file(
            file, description, pid, owner_user_id=current_user_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/list-dir",
    summary="浏览指定目录(虚拟文件系统)",
    response_model=PaginationResponse,
)
async def list_dir(
    pid: str | None = None,
    name: str | None = Query(None, max_length=255, description="名称模糊过滤"),
    pagination: PaginationParams = Depends(),
    current_user_id: str = Depends(require_permission("main", "file", "read")),
    service: FileService = Depends(get_file_service),
) -> PaginationResponse:
    """
    分页浏览指定目录下的子目录与文件(目录排前,名称排序)
    :param pid: 父目录ID(为空表示根目录)
    :param name: 名称模糊过滤(为空不过滤)
    :param pagination: 分页参数
    :param service: 文件服务依赖注入
    :return: 分页响应结果
    """
    try:
        return await service.list_by_pid(pid, pagination, name)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/dirs",
    summary="查询指定目录下的全部子目录(目录树选择用)",
    response_model=list[FileEntry],
)
async def list_dirs(
    pid: str | None = None,
    current_user_id: str = Depends(require_permission("main", "file", "read")),
    service: FileService = Depends(get_file_service),
) -> list[FileEntry]:
    """
    查询指定目录下的全部子目录(不分页,用于移动对话框的目录树懒加载)
    :param pid: 父目录ID(为空表示根目录)
    :param service: 文件服务依赖注入
    :return: 子目录列表
    """
    try:
        return await service.list_dirs(pid)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post(
    "/folder",
    summary="创建目录(虚拟文件系统)",
    status_code=status.HTTP_201_CREATED,
    response_model=FileEntry,
)
async def create_folder(
    name: str = Query(..., min_length=1, max_length=255),
    pid: str | None = None,
    current_user_id: str = Depends(require_permission("main", "file", "create")),
    service: FileService = Depends(get_file_service),
) -> FileEntry:
    """
    在指定目录下创建子目录
    :param name: 目录名称
    :param pid: 父目录ID(为空表示根目录)
    :param current_user_id: 当前登录用户ID(权限依赖注入,目录归属者)
    :param service: 文件服务依赖注入
    :return: 新创建的目录信息
    """
    try:
        return await service.create_folder(name, pid, current_user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put(
    "/entries/{entry_id}",
    summary="更新条目信息(名称变更自动维护路径)",
    response_model=FileEntry,
)
async def update_entry(
    entry_id: str,
    entry_update: FileEntryUpdate,
    current_user_id: str = Depends(require_permission("main", "file", "update")),
    service: FileService = Depends(get_file_service),
) -> FileEntry:
    """
    更新条目描述/名称(名称变更内部走重命名逻辑,保证路径一致)
    :param entry_id: 条目ID
    :param entry_update: 更新数据(name/description)
    :param service: 文件服务依赖注入
    :return: 更新后的条目信息
    """
    try:
        return await service.update(entry_id, entry_update)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put(
    "/entries/{entry_id}/rename",
    summary="重命名条目(目录同步更新子树路径)",
    response_model=FileEntry,
)
async def rename_entry(
    entry_id: str,
    new_name: str = Query(..., min_length=1, max_length=255),
    current_user_id: str = Depends(require_permission("main", "file", "update")),
    service: FileService = Depends(get_file_service),
) -> FileEntry:
    """
    重命名文件或目录(目录重命名时同步更新子树逻辑路径)
    :param entry_id: 条目ID
    :param new_name: 新名称
    :param service: 文件服务依赖注入
    :return: 更新后的条目信息
    """
    try:
        return await service.rename(entry_id, new_name)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put(
    "/entries/{entry_id}/move",
    summary="移动条目到目标目录(目录同步更新子树路径)",
    response_model=FileEntry,
)
async def move_entry(
    entry_id: str,
    target_pid: str | None = Query(None, description="目标父目录ID(为空表示根目录)"),
    current_user_id: str = Depends(require_permission("main", "file", "update")),
    service: FileService = Depends(get_file_service),
) -> FileEntry:
    """
    移动文件或目录到目标目录(含环形引用与同名冲突防护)
    :param entry_id: 条目ID
    :param target_pid: 目标父目录ID(为空表示根目录)
    :param service: 文件服务依赖注入
    :return: 更新后的条目信息
    """
    try:
        return await service.move(entry_id, target_pid)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/download/{entry_id}", summary="下载文件(流式)")
async def download_file(
    entry_id: str,
    current_user_id: str = Depends(require_permission("main", "file", "read")),
    service: FileService = Depends(get_file_service),
):
    """
    流式下载文件
    :param entry_id: 文件条目ID
    :param service: 文件服务依赖注入
    :return: 文件数据流
    """
    try:
        file_name, mime_type, file_key = await service.get_file_info_for_download(
            entry_id
        )
        # 流式返回文件内容(分块读取,支持大文件)
        iter_file = service.stream_file_content(file_key)
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
    current_user_id: str = Depends(require_permission("main", "file", "read")),
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


@router.get("/list", summary="分页查询全部条目", response_model=PaginationResponse)
async def list_files(
    pagination: PaginationParams = Depends(),
    current_user_id: str = Depends(require_permission("main", "file", "read")),
    service: FileService = Depends(get_file_service),
) -> PaginationResponse:
    """
    分页查询全部条目(管理视图)
    :param pagination: 分页参数 (通过查询参数传递)
    :param service: 文件服务依赖注入
    :return: 分页响应结果
    """
    try:
        pagination_response: PaginationResponse = await service.list_paged(pagination)
        return pagination_response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


######################################兼容s3/minio/oss/rustfs对象存储 上传文件######################################
@router.post(
    "/presigned/upload-url",
    summary="生成预签名上传URL(兼容s3/minio/oss/rustfs对象存储)",
    status_code=status.HTTP_200_OK,
)
async def generate_presigned_url_upload(
    presigned_url_request: GeneratePresignedUrlRequest,
    request: Request,
    current_user_id: str = Depends(require_permission("main", "file", "create")),
    service: FileService = Depends(get_file_service),
) -> GeneratePresignedUploadResponse:
    """
    生成预签名URL用于上传文件
    利用SHA-256 的Preimage Resistance达到文件去重妙传和安全性保证
    (新文件要后校验hash值,因为无法确认新文件hash值与文件匹配,默认前端无准确性)
    :param presigned_url_request: 生成预签名URL的请求参数
    :param service: 文件服务依赖注入
    :return: 预签名URL
    """
    try:
        # 直接使用预签名代理端点常量(本地签名拼接完整URL,保证前后端统一)
        presigned_url_path = PRESIGNED_UPLOAD_PROXY_PATH
        base_url = str(request.base_url).rstrip("/")
        generate_presigned_upload_response = (
            await service.generate_presigned_url_upload(
                presigned_url_request, presigned_url_path, base_url
            )
        )
        if generate_presigned_upload_response is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="生成预签名URL失败",
            )
        return generate_presigned_upload_response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put(
    "/presigned/upload/{file_path:path}",
    summary="使用预签名URL上传文件(签名即凭证,免token)",
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
    使用预签名URL上传文件(签名参数即鉴权凭证,不依赖登录态)
    :param file_path: 物理存储键(路径参数)
    :param presigned_upload_params: 预签名上传参数
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post(
    "/presigned/upload-complete",
    summary="上传成功通知,增加条目记录(兼容s3/minio/oss/rustfs对象存储)",
    status_code=status.HTTP_200_OK,
)
async def presigned_url_upload_success(
    file: FileEntryCreate,
    current_user_id: str = Depends(require_permission("main", "file", "create")),
    service: FileService = Depends(get_file_service),
):
    """
    通知后端对象/本地存储完成,新增元数据   防止hash攻击,需要校验文件,符合s3对象存储的hash校验规则
    :param file: 文件条目创建数据
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
    "/files/{file_id}",
    summary="逻辑删除文件(释放内容引用,归零清理物理文件)",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_file(
    file_id: str,
    current_user_id: str = Depends(require_permission("main", "file", "delete")),
    service: FileService = Depends(get_file_service),
):
    """
    删除文件(逻辑删除条目,内容引用计数-1,归零时清理物理文件)
    :param file_id: 文件条目ID
    :param service: 文件服务依赖注入
    """
    try:
        await service.delete_file(file_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.delete(
    "/folders/{folder_id}",
    summary="递归逻辑删除目录(含全部子项)",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_folder(
    folder_id: str,
    current_user_id: str = Depends(require_permission("main", "file", "delete")),
    service: FileService = Depends(get_file_service),
):
    """
    递归删除目录及其全部子项(逻辑删除,内容引用归零时清理物理文件)
    :param folder_id: 目录ID
    :param service: 文件服务依赖注入
    """
    try:
        await service.delete_folder(folder_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


######################################兼容s3/minio/oss/rustfs对象存储 获取文件######################################
@router.get(
    "/entries/{file_entry_id}",
    summary="获取文件或文件夹元数据",
    response_model=FileEntry,
    status_code=status.HTTP_200_OK,
)
async def get_file_entry_info(
    file_entry_id: str,
    current_user_id: str = Depends(require_permission("main", "file", "read")),
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
    "/presigned/download-url/{file_id}",
    summary="生成预签名URL用于下载文件(兼容s3/minio/oss/rustfs对象存储)",
    status_code=status.HTTP_200_OK,
)
async def generate_presigned_url_download(
    file_id: str,
    request: Request,
    current_user_id: str = Depends(require_permission("main", "file", "read")),
    service: FileService = Depends(get_file_service),
) -> GeneratePresignedDownloadResponse:
    """
    生成预签名URL用于下载文件
    :param file_id: 文件条目ID
    :param service: 文件服务依赖注入
    :return: 预签名URL
    """
    try:
        # 直接使用预签名代理端点常量(本地签名拼接完整URL,保证前后端统一)
        presigned_url_path = PRESIGNED_DOWNLOAD_PROXY_PATH
        base_url = str(request.base_url).rstrip("/")
        generate_presigned_download_response = (
            await service.generate_presigned_url_download(
                file_id, presigned_url_path, base_url
            )
        )
        if generate_presigned_download_response is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文件不存在或生成预签名URL失败",
            )
        return generate_presigned_download_response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/presigned/download/{file_path:path}",
    summary="使用预签名URL下载文件(签名即凭证,免token)",
    status_code=status.HTTP_200_OK,
)
async def download_with_presigned_url(
    file_path: str,
    presigned_download_params: PresignedDownloadParams = Depends(),
    service: FileService = Depends(get_file_service),
) -> Response:
    """
    使用预签名URL下载文件(签名参数即鉴权凭证,不依赖登录态)
    :param file_path: 物理存储键(路径参数)
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


######################################路径操作/搜索/复制/统计/迁移######################################
@router.get(
    "/path",
    summary="按逻辑路径查询条目(路径导航用)",
    response_model=FileEntry,
    status_code=status.HTTP_200_OK,
)
async def get_entry_by_path(
    path: str = Query(..., min_length=1, max_length=2000, description="逻辑路径(如 /docs/readme.md)"),
    current_user_id: str = Depends(require_permission("main", "file", "read")),
    service: FileService = Depends(get_file_service),
) -> FileEntry:
    """
    按逻辑路径精确查询文件或目录(不存在返回404)
    :param path: 逻辑路径
    :param service: 文件服务依赖注入
    :return: 条目元数据
    """
    result = await service.get_by_path(path)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"路径不存在: {path}"
        )
    return result


@router.get(
    "/list-by-path",
    summary="按逻辑路径浏览目录(目录排前,名称排序)",
    response_model=PaginationResponse,
)
async def list_by_path(
    path: str = Query(..., min_length=1, max_length=2000, description="目录逻辑路径"),
    name: str | None = Query(None, max_length=255, description="名称模糊过滤"),
    pagination: PaginationParams = Depends(),
    current_user_id: str = Depends(require_permission("main", "file", "read")),
    service: FileService = Depends(get_file_service),
) -> PaginationResponse:
    """
    按逻辑路径分页浏览目录(无需先查目录ID)
    :param path: 目录逻辑路径
    :param name: 名称模糊过滤
    :param pagination: 分页参数
    :param service: 文件服务依赖注入
    :return: 分页响应结果
    """
    try:
        return await service.list_by_path(path, pagination, name)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post(
    "/mkdir-p",
    summary="按逻辑路径递归创建目录(mkdir -p 语义,已存在直接返回)",
    status_code=status.HTTP_201_CREATED,
    response_model=FileEntry,
)
async def mkdir_p(
    path: str = Query(..., min_length=1, max_length=2000, description="目录路径(如 /docs/images,多级一次创建)"),
    current_user_id: str = Depends(require_permission("main", "file", "create")),
    service: FileService = Depends(get_file_service),
) -> FileEntry:
    """
    递归创建目录层级,中间层已存在则复用
    :param path: 目录逻辑路径
    :param current_user_id: 当前登录用户ID(目录归属者)
    :param service: 文件服务依赖注入
    :return: 最终层目录条目
    """
    try:
        return await service.mkdir_p(path, owner_user_id=current_user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/search",
    summary="全树模糊搜索条目(匹配名称或逻辑路径)",
    response_model=PaginationResponse,
)
async def search_entries(
    keyword: str = Query(..., min_length=1, max_length=255, description="搜索关键字"),
    pagination: PaginationParams = Depends(),
    current_user_id: str = Depends(require_permission("main", "file", "read")),
    service: FileService = Depends(get_file_service),
) -> PaginationResponse:
    """
    全树搜索文件与目录(目录排前,路径排序)
    :param keyword: 搜索关键字
    :param pagination: 分页参数
    :param service: 文件服务依赖注入
    :return: 分页响应结果
    """
    try:
        return await service.search(keyword, pagination)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post(
    "/copy",
    summary="复制条目(文件指向同一内容哈希,目录递归整树复制)",
    status_code=status.HTTP_201_CREATED,
    response_model=FileEntry,
)
async def copy_entry(
    entry_id: str = Query(..., description="源条目ID"),
    target_pid: str | None = Query(None, description="目标父目录ID(为空表示根目录)"),
    current_user_id: str = Depends(require_permission("main", "file", "create")),
    service: FileService = Depends(get_file_service),
) -> FileEntry:
    """
    复制文件或目录到目标目录(内容哈希去重,物理文件不重复占用存储)
    :param entry_id: 源条目ID
    :param target_pid: 目标父目录ID
    :param current_user_id: 当前登录用户ID
    :param service: 文件服务依赖注入
    :return: 复制出的新条目
    """
    try:
        return await service.copy_entry(entry_id, target_pid, current_user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/stats",
    summary="存储统计(条目数/物理内容数/总占用/当前存储类型)",
    response_model=dict,
    status_code=status.HTTP_200_OK,
)
async def get_stats(
    current_user_id: str = Depends(require_permission("main", "file", "read")),
    service: FileService = Depends(get_file_service),
) -> dict:
    """
    获取虚拟文件系统与物理存储统计信息
    :param service: 文件服务依赖注入
    :return: 统计信息(StorageStats)
    """
    try:
        return (await service.get_stats()).model_dump()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post(
    "/migrate",
    summary="存储迁移(local<->rustfs/s3 物理内容搬运,切换配置前调用)",
    response_model=dict,
    status_code=status.HTTP_200_OK,
)
async def migrate_storage(
    req: MigrateRequest,
    current_user_id: str = Depends(require_permission("main", "file", "migrate")),
    service: FileService = Depends(get_file_service),
) -> dict:
    """
    把源存储的全部物理内容搬运到目标存储(逻辑条目不变,支持断点续迁)
    典型流程: 1.调用本接口迁移 2.修改 config storage_type 3.重启服务
    :param req: 迁移请求(from_type/to_type)
    :param service: 文件服务依赖注入
    :return: 迁移结果 {total, migrated, skipped, failed}
    """
    try:
        return await service.migrate_storage(req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# 将路由注册到模块应用
module_app.include_router(router, prefix="/filesystem", tags=["文件管理"])
