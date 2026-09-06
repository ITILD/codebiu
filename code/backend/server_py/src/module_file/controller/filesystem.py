from module_file.config.server import module_app
from module_file.dependencies.filesystem import (
    get_file_service,
    get_managed_file_service,
    get_download_user_id,
)
from module_file.service.filesystem import FileService, BusinessEntryError
from module_file.do.filesystem import (
    FileEntry,
    FileEntryUpdate,
    MultipartInitRequest,
    MultipartInitResponse,
    MultipartPartInfo,
    MultipartCompleteRequest,
    EntryCreateRequest,
    UploadModeResponse,
    MigrateRequest,
)
from module_authorization.dependencies.permission import require_permission
from common.utils.db.schema.pagination import PaginationParams, PaginationResponse

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
from fastapi.responses import StreamingResponse, RedirectResponse

router = APIRouter()


@router.post(
    "/upload",
    summary="上传文件到指定目录(小文件直传,内容哈希去重)",
    status_code=status.HTTP_201_CREATED,
    response_model=FileEntry,
)
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    description: str = None,
    pid: str = None,
    current_user_id: str = Depends(require_permission("main", "file", "create")),
    service: FileService = Depends(get_managed_file_service),
) -> FileEntry:
    """
    上传文件到指定目录(虚拟文件系统,仅限小文件)
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
    service: FileService = Depends(get_managed_file_service),
) -> FileEntry:
    """
    在指定目录下创建子目录
    :param name: 目录名称
    :param pid: 父目录ID(为空表示根目录)
    :param current_user_id: 当前登录用户ID(目录归属者)
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
    service: FileService = Depends(get_managed_file_service),
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
    service: FileService = Depends(get_managed_file_service),
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
    service: FileService = Depends(get_managed_file_service),
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


@router.get("/upload-mode", summary="查询上传模式(direct直传/proxy中转)", response_model=UploadModeResponse)
async def get_upload_mode(
    current_user_id: str = Depends(require_permission("main", "file", "read")),
    service: FileService = Depends(get_file_service),
) -> UploadModeResponse:
    """
    查询当前存储的上传模式(前端启动时获取一次并缓存)
    - direct: S3协议存储,前端预签名直传,数据面不经过服务端
    - proxy: 本地磁盘存储,数据面经服务端中转
    :param service: 文件服务依赖注入
    :return: 上传模式/分片大小/小文件直传上限
    """
    return service.get_upload_mode()


@router.get("/download/{entry_id}", summary="下载文件(s3直链302/local流式)")
async def download_file(
    entry_id: str,
    current_user_id: str | None = Depends(get_download_user_id),
    service: FileService = Depends(get_file_service),
):
    """
    下载文件: 权限与元数据校验后按存储类型分流
    - S3协议存储: 签发预签名GET直链,302重定向浏览器直连对象存储(数据面不经过服务端)
    - 本地磁盘: 服务端流式代理(分块读取,支持大文件)
    :param entry_id: 文件条目ID
    :param service: 文件服务依赖注入
    :return: 302重定向(直链) 或 文件数据流(代理)
    """
    try:
        file_name, mime_type, file_key = await service.get_file_info_for_download(
            entry_id
        )
        # 直传存储: 预签名直链重定向(浏览器直连,服务端零流量)
        url = await service.presign_download_url(file_key, file_name)
        if url:
            return RedirectResponse(url, status_code=status.HTTP_302_FOUND)
        # 本地存储: 流式返回文件内容(分块读取,支持大文件)
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


######################################分片上传(multipart,大文件 >10MB 自动)######################################
@router.post(
    "/multipart/init",
    summary="初始化分片上传(大文件,内容已存在时秒传)",
    status_code=status.HTTP_200_OK,
    response_model=MultipartInitResponse,
)
async def init_multipart_upload(
    req: MultipartInitRequest,
    current_user_id: str = Depends(require_permission("main", "file", "create")),
    service: FileService = Depends(get_managed_file_service),
) -> MultipartInitResponse:
    """
    初始化分片上传会话(前端对 >10MB 文件自动分流调用)
    :param req: 初始化请求(文件名/大小/SHA-256/父目录)
    :param current_user_id: 当前登录用户ID(文件归属者)
    :param service: 文件服务依赖注入
    :return: 会话凭证与建议分片大小(is_existing=True 时直接调 /upload-complete 秒传)
    """
    try:
        return await service.init_multipart_upload(req, owner_user_id=current_user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put(
    "/multipart/{upload_id}/parts/{part_number}",
    summary="上传分片(凭证即会话)",
    status_code=status.HTTP_200_OK,
    response_model=MultipartPartInfo,
)
async def upload_multipart_part(
    upload_id: str,
    part_number: int,
    request: Request,
    current_user_id: str = Depends(require_permission("main", "file", "create")),
    service: FileService = Depends(get_managed_file_service),
) -> MultipartPartInfo:
    """
    上传单个分片(最后一片可小于标准分片大小)
    :param upload_id: 分片会话凭证(init 返回)
    :param part_number: 分片号(从1开始)
    :param request: 请求体为分片二进制内容
    :param service: 文件服务依赖注入
    :return: 分片信息(part_number/etag/size)
    """
    try:
        content: bytes = await request.body()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="分片内容不能为空"
            )
        return await service.upload_multipart_part(upload_id, part_number, content)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/multipart/{upload_id}/parts",
    summary="查询已上传分片(断点续传)",
    status_code=status.HTTP_200_OK,
    response_model=list[MultipartPartInfo],
)
async def list_multipart_parts(
    upload_id: str,
    current_user_id: str = Depends(require_permission("main", "file", "read")),
    service: FileService = Depends(get_file_service),
) -> list[MultipartPartInfo]:
    """
    查询会话中已上传的分片列表(上传中断后可续传)
    :param upload_id: 分片会话凭证
    :param service: 文件服务依赖注入
    :return: 分片信息列表
    """
    try:
        return await service.list_multipart_parts(upload_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post(
    "/multipart/{upload_id}/complete",
    summary="完成分片上传(合并分片并创建条目)",
    status_code=status.HTTP_201_CREATED,
    response_model=FileEntry,
)
async def complete_multipart_upload(
    upload_id: str,
    req: MultipartCompleteRequest,
    current_user_id: str = Depends(require_permission("main", "file", "create")),
    service: FileService = Depends(get_managed_file_service),
) -> FileEntry:
    """
    通知后端合并分片并创建文件条目(服务端校验内容SHA-256防伪造)
    :param upload_id: 分片会话凭证
    :param req: 完成请求(文件名/分片列表)
    :param current_user_id: 当前登录用户ID(文件归属者)
    :param service: 文件服务依赖注入
    :return: 创建的文件条目
    """
    try:
        return await service.complete_multipart_upload(
            upload_id, req, owner_user_id=current_user_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.delete(
    "/multipart/{upload_id}",
    summary="取消分片上传(清理已上传分片)",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def abort_multipart_upload(
    upload_id: str,
    current_user_id: str = Depends(require_permission("main", "file", "delete")),
    service: FileService = Depends(get_managed_file_service),
):
    """
    取消分片上传会话并清理存储侧已上传的分片
    :param upload_id: 分片会话凭证
    :param service: 文件服务依赖注入
    """
    try:
        await service.abort_multipart_upload(upload_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post(
    "/upload-complete",
    summary="秒传建条目(内容已存在时直接创建文件记录)",
    status_code=status.HTTP_201_CREATED,
    response_model=FileEntry,
)
async def create_entry(
    req: EntryCreateRequest,
    current_user_id: str = Depends(require_permission("main", "file", "create")),
    service: FileService = Depends(get_managed_file_service),
) -> FileEntry:
    """
    基于已完成的内容记录创建文件条目(multipart/init 返回 is_existing=True 后调用)
    :param req: 条目创建请求(文件名/内容SHA-256)
    :param current_user_id: 当前登录用户ID(文件归属者)
    :param service: 文件服务依赖注入
    :return: 创建的文件条目
    """
    try:
        return await service.create_entry(req, owner_user_id=current_user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


######################################删除逻辑######################################
@router.delete(
    "/files/{file_id}",
    summary="逻辑删除文件(释放内容引用,归零清理物理文件)",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_file(
    file_id: str,
    current_user_id: str = Depends(require_permission("main", "file", "delete")),
    service: FileService = Depends(get_managed_file_service),
):
    """
    删除文件(逻辑删除条目,内容引用计数-1,归零时清理物理文件)
    :param file_id: 文件条目ID
    :param service: 文件服务依赖注入
    """
    try:
        await service.delete_file(file_id)
    except BusinessEntryError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
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
    service: FileService = Depends(get_managed_file_service),
):
    """
    递归删除目录及其全部子项(逻辑删除,内容引用归零时清理物理文件)
    :param folder_id: 目录ID
    :param service: 文件服务依赖注入
    """
    try:
        await service.delete_folder(folder_id)
    except BusinessEntryError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


######################################获取文件元数据######################################
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
    service: FileService = Depends(get_managed_file_service),
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
    service: FileService = Depends(get_managed_file_service),
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
    summary="存储迁移(local<->s3 物理内容搬运,切换配置前调用)",
    response_model=dict,
    status_code=status.HTTP_200_OK,
)
async def migrate_storage(
    req: MigrateRequest,
    current_user_id: str = Depends(require_permission("main", "file", "migrate")),
    service: FileService = Depends(get_managed_file_service),
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
