from fastapi import (
    APIRouter,
    status,
    Depends,
    UploadFile,
    File,
    Form,
    Query,
    Request,
)
from common.utils.fastapiEX.exceptions import BusinessError, NotFoundError
from fastapi.responses import RedirectResponse, StreamingResponse
from pathlib import Path
import logging

from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_rag.do.project_document import (
    ProjectDocument,
    ProjectDocumentUpdate,
    ProjectDocumentResponse,
    DocumentIngestProgress,
)
from module_rag.service.project_document import ProjectDocumentService
from module_rag.dependencies.project_document import get_project_document_service
from module_authorization.dependencies.auth import get_current_user_id
from module_rag.dependencies.permission import (
    enforce_project_permission,
    require_project_permission,
)
from module_rag.config.server import module_app
# 确保导入你修改后的 DocType
from module_rag.do.project_document import DocType
from module_file.utils.base.file_utils import FileUtils
from module_file.do.filesystem import (
    EntryCreateRequest,
    FileEntry,
    MultipartCompleteRequest,
    MultipartInitRequest,
    MultipartInitResponse,
    MultipartPartInfo,
    UploadModeResponse,
)
from module_file.service.filesystem import FileService
from module_file.dependencies.filesystem import get_file_service
from module_task.do.task import TaskQueueCreate
from module_task.service.task import TaskQueueService
from module_task.dependencies.task import get_task_queue_service

router = APIRouter()

logger = logging.getLogger(__name__)


async def _dispatch_parse_task(
    service: ProjectDocumentService,
    task_service: TaskQueueService,
    document: ProjectDocument,
    current_user_id: str,
) -> str | None:
    """上传成功后自动派发异步解析任务("上传即解析", 各登记口径共用)
    推送任务队列前先校验所需模型(对话+向量化), 缺失时不派发并返回告警文案
    :return: 告警文案(模型缺失/派发失败), 成功返回 None
    """
    try:
        missing = await service.ensure_parse_models(current_user_id)
        if missing:
            return (
                f"文档已上传, 但解析任务未派发: 未配置可用的{'、'.join(missing)}模型, "
                "请先在模型管理中绑定或由管理员配置默认公共模型"
            )
        # 经统一任务队列(task_queue 表可查/可取消/可重试), 任务以创建者绑定的模型执行
        await task_service.create(
            TaskQueueCreate(
                name=f"解析文档: {document.name}",
                task_type="rag_document_parse",
                payload={"document_id": document.id},
            ),
            current_user_id,
        )
        return None
    except Exception as e:
        # Celery 不可用时静默降级: 文档保持 pending, 可手动触发解析
        logger.warning(f"自动派发解析任务失败(可手动解析) document_id={document.id}: {e}")
        return f"文档已上传, 但解析任务派发失败(可手动重试): {e}"


@router.post(
    "/{project_id}/upload",
    summary="上传文档到项目(小文件直传口径)",
    status_code=status.HTTP_201_CREATED,
    response_model=ProjectDocumentResponse,
)
async def upload_project_document(
    project_id: str,
    file: UploadFile,
    description: str | None = Form(default=None, description="文档描述(可选)"),
    pid: str | None = Form(default=None, description="父目录ID(为空上传到项目根文件夹)"),
    current_user_id: str = Depends(require_project_permission("doc", "upload")),
    service: ProjectDocumentService = Depends(get_project_document_service),
    task_service: TaskQueueService = Depends(get_task_queue_service),
) -> ProjectDocumentResponse:
    """
    上传文档到指定项目(条目级: 经统一文件服务在虚拟目录 /知识库/<项目名>/ 下建条目,
    project_document 记录知识库口径; 大文件请走 /multipart 分片流程)
    :param project_id: 项目ID
    :param file: 上传的文件(支持 pdf/docx/xlsx/pptx 等常见文档格式)
    :param description: 文档描述
    :param pid: 父目录ID(为空上传到项目根文件夹, 须属于项目子树)
    :param current_user_id: 当前登录用户ID(由 token 自动解析)
    :param service: 文档服务依赖注入
    :param task_service: 统一任务队列服务依赖注入
    :return: 文档元数据(parse_task_warning 携带解析任务派发警告)
    """
    document = await service.upload_document(
        project_id, file, current_user_id, description, pid
    )
    # 上传成功后自动派发异步解析任务(模型缺失/队列不可用时返回告警)
    response = ProjectDocumentResponse.model_validate(document.model_dump())
    response.parse_task_warning = await _dispatch_parse_task(
        service, task_service, document, current_user_id
    )
    return response


@router.get(
    "/{project_id}/list",
    summary="分页查询项目文档列表",
    response_model=PaginationResponse,
)
async def list_project_documents(
    project_id: str,
    pagination: PaginationParams = Depends(),
    name: str | None = Query(None, max_length=255, description="文档名称模糊搜索"),
    parse_status: str | None = Query(None, description="解析状态过滤(pending/parsing/completed/failed)"),
    current_user_id: str = Depends(require_project_permission("doc", "read")),
    service: ProjectDocumentService = Depends(get_project_document_service),
) -> PaginationResponse:
    """
    分页查询项目文档列表(支持多字段过滤)
    :param project_id: 项目ID
    :param pagination: 分页参数
    :param name: 文档名称模糊搜索
    :param parse_status: 解析状态过滤(pending/parsing/completed/failed)
    :param service: 文档服务依赖注入
    :return: 分页文档列表
    """
    return await service.list_by_project(
        project_id, pagination, name=name, parse_status=parse_status
    )


@router.get(
    "/supported-types",
    summary="获取支持上传的文件格式列表",
    description="返回系统支持的所有文件格式，按文档、图片、音频、视频分类，供前端渲染上传组件使用。"
)
async def get_supported_file_types():
    """
    返回支持上传的文件格式, 按文档/图片/音频/视频四类分组,
    并附 all_extensions 扁平列表供前端直接用于 input accept 属性
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


######################################统一存储上传流程(与文件管理共用一套 direct/proxy 分片链路)######################################
@router.get(
    "/upload-mode",
    summary="查询知识库文档上传模式(direct预签名直传/proxy服务端中转)",
    response_model=UploadModeResponse,
)
async def get_rag_upload_mode(
    current_user_id: str = Depends(get_current_user_id),
    file_service: FileService = Depends(get_file_service),
) -> UploadModeResponse:
    """
    查询当前存储的上传模式(前端启动时获取一次并缓存)
    - direct: S3协议存储,前端预签名直传,数据面不经过服务端
    - proxy: 本地磁盘存储,数据面经服务端中转
    :param file_service: 统一文件存储服务依赖注入
    :return: 上传模式/分片大小/小文件直传上限
    """
    return file_service.get_upload_mode()


@router.get(
    "/model-check",
    summary="校验当前用户解析文档所需模型是否可用",
)
async def check_rag_parse_models(
    current_user_id: str = Depends(get_current_user_id),
    service: ProjectDocumentService = Depends(get_project_document_service),
) -> dict:
    """
    校验解析流水线所需模型(对话+向量化)是否存在(用户绑定或默认公共模型回退),
    供前端在提交解析任务前弹窗警告
    :param current_user_id: 当前登录用户ID(由 token 自动解析)
    :param service: 文档服务依赖注入
    :return: {ok, missing(缺失模型中文名列表), message(为空表示可用)}
    """
    missing = await service.ensure_parse_models(current_user_id)
    return {
        "ok": not missing,
        "missing": missing,
        "message": None
        if not missing
        else f"未配置可用的{'、'.join(missing)}模型, 无法解析文档; 请先在模型管理中绑定或由管理员配置默认公共模型",
    }


@router.post(
    "/{project_id}/multipart/init",
    summary="初始化文档分片上传(大文件/直传口径, 内容已存在时秒传)",
    response_model=MultipartInitResponse,
)
async def init_rag_document_multipart(
    project_id: str,
    req: MultipartInitRequest,
    current_user_id: str = Depends(require_project_permission("doc", "upload")),
    service: ProjectDocumentService = Depends(get_project_document_service),
) -> MultipartInitResponse:
    """
    初始化上传会话(凭证签发阶段完成秒传判断/内容登记/预签名, 复用统一文件存储流程)
    :param project_id: 项目ID
    :param req: 初始化请求(文件名/大小/SHA-256/MIME)
    :return: 会话凭证与上传模式(is_existing=True 时直接调 /upload-complete 秒传登记)
    """
    return await service.init_multipart_upload(
        project_id, req, owner_user_id=current_user_id
    )


@router.put(
    "/{project_id}/multipart/{upload_id}/parts/{part_number}",
    summary="上传文档分片(proxy中转模式, 凭证即会话)",
    response_model=MultipartPartInfo,
)
async def upload_rag_document_part(
    project_id: str,
    upload_id: str,
    part_number: int,
    request: Request,
    current_user_id: str = Depends(require_project_permission("doc", "upload")),
    file_service: FileService = Depends(get_file_service),
) -> MultipartPartInfo:
    """
    中转上传单个分片(direct 模式前端直传对象存储,不经服务端)
    :param upload_id: 分片会话凭证(init 返回)
    :param part_number: 分片号(从1开始)
    :param request: 请求体为分片二进制内容
    :return: 分片信息(part_number/etag/size)
    """
    content: bytes = await request.body()
    if not content:
        raise BusinessError("分片内容不能为空")
    return await file_service.upload_multipart_part(upload_id, part_number, content)


@router.get(
    "/{project_id}/multipart/{upload_id}/parts",
    summary="查询文档已上传分片(断点续传)",
    response_model=list[MultipartPartInfo],
)
async def list_rag_document_parts(
    project_id: str,
    upload_id: str,
    current_user_id: str = Depends(require_project_permission("doc", "read")),
    file_service: FileService = Depends(get_file_service),
) -> list[MultipartPartInfo]:
    """
    查询会话中已上传的分片列表(上传中断后可续传)
    :param upload_id: 分片会话凭证
    :return: 分片信息列表
    """
    return await file_service.list_multipart_parts(upload_id)


@router.post(
    "/{project_id}/multipart/{upload_id}/complete",
    summary="完成文档分片上传(对账合并并按知识库口径登记)",
    status_code=status.HTTP_201_CREATED,
    response_model=ProjectDocumentResponse,
)
async def complete_rag_document_multipart(
    project_id: str,
    upload_id: str,
    req: MultipartCompleteRequest,
    current_user_id: str = Depends(require_project_permission("doc", "upload")),
    service: ProjectDocumentService = Depends(get_project_document_service),
    task_service: TaskQueueService = Depends(get_task_queue_service),
) -> ProjectDocumentResponse:
    """
    通知后端合并分片并创建知识库文档记录(服务端校验内容SHA-256防伪造)
    :param project_id: 项目ID
    :param upload_id: 分片会话凭证
    :param req: 完成请求(文件名/分片列表/描述)
    :return: 创建的文档元数据(parse_task_warning 携带解析任务派发警告)
    """
    document = await service.complete_multipart_upload(
        project_id, upload_id, req, current_user_id
    )
    # 登记成功后自动派发异步解析任务(模型缺失/队列不可用时返回告警)
    response = ProjectDocumentResponse.model_validate(document.model_dump())
    response.parse_task_warning = await _dispatch_parse_task(
        service, task_service, document, current_user_id
    )
    return response


@router.delete(
    "/{project_id}/multipart/{upload_id}",
    summary="取消文档分片上传(清理已上传分片)",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def abort_rag_document_multipart(
    project_id: str,
    upload_id: str,
    current_user_id: str = Depends(require_project_permission("doc", "delete")),
    file_service: FileService = Depends(get_file_service),
):
    """
    取消分片上传会话并清理存储侧已上传的分片
    :param upload_id: 分片会话凭证(init 返回)
    """
    await file_service.abort_multipart_upload(upload_id)


@router.post(
    "/{project_id}/upload-complete",
    summary="秒传登记(内容已存在时直接创建知识库文档记录)",
    status_code=status.HTTP_201_CREATED,
    response_model=ProjectDocumentResponse,
)
async def complete_rag_document_entry(
    project_id: str,
    req: EntryCreateRequest,
    current_user_id: str = Depends(require_project_permission("doc", "upload")),
    service: ProjectDocumentService = Depends(get_project_document_service),
    task_service: TaskQueueService = Depends(get_task_queue_service),
) -> ProjectDocumentResponse:
    """
    基于已存在的内容记录创建知识库文档记录(multipart/init 返回 is_existing=True 后调用)
    :param project_id: 项目ID
    :param req: 登记请求(文件名/内容SHA-256/大小/描述)
    :return: 创建的文档元数据(parse_task_warning 携带解析任务派发警告)
    """
    document = await service.create_document_from_content(
        project_id, req, current_user_id
    )
    # 秒传登记成功后同样自动派发解析任务(与其他上传口径一致)
    response = ProjectDocumentResponse.model_validate(document.model_dump())
    response.parse_task_warning = await _dispatch_parse_task(
        service, task_service, document, current_user_id
    )
    return response


######################################知识库文件夹与条目浏览(虚拟目录条目级)######################################
@router.get(
    "/{project_id}/entries",
    summary="浏览项目内文件夹与文件(目录排前,名称排序)",
    response_model=PaginationResponse,
)
async def list_project_entries(
    project_id: str,
    pagination: PaginationParams = Depends(),
    pid: str | None = Query(None, description="父目录ID(为空浏览项目根文件夹)"),
    name: str | None = Query(None, max_length=255, description="名称模糊过滤"),
    current_user_id: str = Depends(require_project_permission("doc", "read")),
    service: ProjectDocumentService = Depends(get_project_document_service),
) -> PaginationResponse:
    """
    分页浏览项目内文件夹与文件(条目级新口径, 目录排前名称排序)
    :param project_id: 项目ID
    :param pagination: 分页参数
    :param pid: 父目录ID(为空浏览项目根文件夹, 须属于项目子树)
    :param name: 名称模糊过滤
    :param current_user_id: 当前登录用户ID(由 token 自动解析)
    :param service: 文档服务依赖注入
    :return: 分页条目列表(FileEntry)
    """
    return await service.list_entries(project_id, pagination, pid=pid, name=name)


@router.post(
    "/{project_id}/folders",
    summary="在项目内创建文件夹",
    status_code=status.HTTP_201_CREATED,
    response_model=FileEntry,
)
async def create_project_folder(
    project_id: str,
    name: str = Query(..., min_length=1, max_length=255, description="文件夹名称(1-255字符)"),
    pid: str | None = Query(None, description="父目录ID(为空创建到项目根文件夹)"),
    current_user_id: str = Depends(require_project_permission("doc", "upload")),
    service: ProjectDocumentService = Depends(get_project_document_service),
) -> FileEntry:
    """
    在项目虚拟目录内创建子文件夹(条目级, source_module 继承 rag 模块标记)
    :param project_id: 项目ID
    :param name: 文件夹名称
    :param pid: 父目录ID(为空创建到项目根文件夹, 须属于项目子树)
    :param current_user_id: 当前登录用户ID(条目归属者)
    :param service: 文档服务依赖注入
    :return: 新创建的文件夹条目
    """
    return await service.create_folder(project_id, name, current_user_id, pid)


@router.put(
    "/{project_id}/folders/{folder_id}",
    summary="重命名项目内文件夹",
    response_model=FileEntry,
)
async def rename_project_folder(
    project_id: str,
    folder_id: str,
    name: str = Query(..., min_length=1, max_length=255, description="文件夹新名称(1-255字符)"),
    current_user_id: str = Depends(require_project_permission("doc", "update")),
    service: ProjectDocumentService = Depends(get_project_document_service),
) -> FileEntry:
    """
    重命名项目内子文件夹(同步更新子树逻辑路径; 项目根文件夹请改项目名)
    :param project_id: 项目ID
    :param folder_id: 文件夹条目ID
    :param name: 新名称
    :param current_user_id: 当前登录用户ID(由 token 自动解析)
    :param service: 文档服务依赖注入
    :return: 更新后的文件夹条目
    """
    return await service.rename_folder(project_id, folder_id, name)


@router.delete(
    "/{project_id}/folders/{folder_id}",
    summary="删除项目内文件夹(递归删除条目并释放内容引用)",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_project_folder(
    project_id: str,
    folder_id: str,
    current_user_id: str = Depends(require_project_permission("doc", "delete")),
    service: ProjectDocumentService = Depends(get_project_document_service),
):
    """
    递归删除项目内子文件夹及其全部子项(内容引用归零时清理物理文件;
    文档记录与向量不在此清理, 属文档级操作)
    :param project_id: 项目ID
    :param folder_id: 文件夹条目ID
    :param current_user_id: 当前登录用户ID(由 token 自动解析)
    :param service: 文档服务依赖注入
    """
    await service.delete_folder(project_id, folder_id)


######################################文档详情/进度/下载/编辑/删除/解析######################################
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
    document = await service.get_document(document_id)
    if not document:
        raise NotFoundError("文档不存在")
    # 权限校验: 通过文档解析所属项目
    await enforce_project_permission(
        current_user_id, document.project_id, "doc", "read"
    )
    return ProjectDocumentResponse.model_validate(document.model_dump())


@router.get(
    "/{document_id}/progress",
    summary="查询文档入库步骤与进度",
    response_model=DocumentIngestProgress,
)
async def get_project_document_progress(
    document_id: str,
    current_user_id: str = Depends(get_current_user_id),
    service: ProjectDocumentService = Depends(get_project_document_service),
) -> DocumentIngestProgress:
    """
    查询文档入库流水线的步骤与进度(解析→拆分chunk→向量化, 预留图谱化/标签抽取/网络检索合并),
    供前端轮询渲染步骤条; 步骤注册表扩展后本接口自动返回新步骤
    :param document_id: 文档ID
    :param current_user_id: 当前登录用户ID(由 token 自动解析)
    :param service: 文档服务依赖注入
    :return: 入库步骤明细与加权总进度
    """
    document = await service.get_document(document_id)
    if not document:
        raise NotFoundError("文档不存在")
    # 权限校验: 通过文档解析所属项目
    await enforce_project_permission(
        current_user_id, document.project_id, "doc", "read"
    )
    return service.build_ingest_progress(document)


@router.get(
    "/{document_id}/download",
    summary="下载文档(S3预签名直链302/本地流式)",
)
async def download_project_document(
    document_id: str,
    current_user_id: str = Depends(get_current_user_id),
    service: ProjectDocumentService = Depends(get_project_document_service),
    file_service: FileService = Depends(get_file_service),
):
    """
    下载文档(双口径): 统一存储口径按存储类型分流(S3 302直链/local 流式代理),
    旧口径本地文件直接流式返回
    :param document_id: 文档ID
    :param current_user_id: 当前登录用户ID(由 token 自动解析)
    :param service: 文档服务依赖注入
    :param file_service: 统一文件存储服务依赖注入
    :return: 302重定向(直链) 或 文件数据流(代理)
    """
    # 权限校验: 通过文档解析所属项目
    document = await service.get_document(document_id)
    if not document:
        raise NotFoundError("文档不存在")
    await enforce_project_permission(
        current_user_id, document.project_id, "doc", "read"
    )
    file_name, mime_type, source, storage_backed = (
        await service.get_file_for_download(document_id)
    )
    # Content-Disposition: ASCII 回退 + RFC 5987 filename*(支持中文等非 ASCII 文件名)
    from urllib.parse import quote

    ascii_fallback = file_name.encode("ascii", "ignore").decode() or "download"
    encoded_name = quote(file_name)
    headers = {
        "Content-Disposition": (
            f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded_name}"
        )
    }
    if storage_backed:
        # 统一存储口径: S3 签发预签名直链 302 重定向(服务端零流量); local 流式代理
        url = await file_service.presign_download_url(str(source), file_name)
        if url:
            return RedirectResponse(url, status_code=status.HTTP_302_FOUND)
        return StreamingResponse(
            file_service.stream_file_content(str(source)),
            media_type=mime_type or "application/octet-stream",
            headers=headers,
        )
    # 旧口径: DIR_UPLOAD 本地文件流式返回
    return StreamingResponse(
        FileUtils.read_file_stream(source),
        media_type=mime_type or "application/octet-stream",
        headers=headers,
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
    # 权限校验: 通过文档解析所属项目
    doc_info = await service.get_document(document_id)
    if not doc_info:
        raise NotFoundError("文档不存在")
    await enforce_project_permission(
        current_user_id, doc_info.project_id, "doc", "update"
    )
    await service.update(document_id, document)


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
    删除文档(释放物理内容与数据库记录; 统一存储口径按引用计数清理)
    :param document_id: 文档ID
    :param current_user_id: 当前登录用户ID(由 token 自动解析)
    :param service: 文档服务依赖注入
    """
    # 权限校验: 通过文档解析所属项目
    doc_info = await service.get_document(document_id)
    if not doc_info:
        raise NotFoundError("文档不存在")
    await enforce_project_permission(
        current_user_id, doc_info.project_id, "doc", "delete"
    )
    await service.delete_document(document_id)


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
    # 权限校验: 通过文档解析所属项目
    doc_info = await service.get_document(document_id)
    if not doc_info:
        raise NotFoundError("文档不存在")
    await enforce_project_permission(
        current_user_id, doc_info.project_id, "doc", "update"
    )
    # return await service.reparse_document(document_id, current_user_id)
    return await service.parse_document(document_id, current_user_id)

@router.post(
    "/{document_id}/reparse-task",
    summary="重新解析文档加入任务队列",
)
async def reparse_project_document_task(
    document_id: str,
    current_user_id: str = Depends(get_current_user_id),
    service: ProjectDocumentService = Depends(get_project_document_service),
    task_service: TaskQueueService = Depends(get_task_queue_service),
) -> dict:
    """
    重新解析文档(经统一任务队列异步执行; 直跑版本见 /{document_id}/reparse)
    推送任务队列前先校验所需模型(对话+向量化), 缺失时返回 400 供前端弹窗警告
    :param document_id: 文档ID
    :param current_user_id: 当前登录用户ID(任务以其绑定模型执行)
    :param service: 文档服务依赖注入
    :param task_service: 统一任务队列服务依赖注入
    :return: 任务提交结果(含 task_queue 任务ID, 可在任务队列页跟踪)
    """
    # 权限校验: 通过文档解析所属项目
    doc_info = await service.get_document(document_id)
    if not doc_info:
        raise NotFoundError("文档不存在")
    await enforce_project_permission(
        current_user_id, doc_info.project_id, "doc", "update"
    )
    # 模型预检: 对话+向量化模型缺失时拒绝入队(前端弹窗提示)
    missing = await service.ensure_parse_models(current_user_id)
    if missing:
        raise BusinessError(
            f"未配置可用的{'、'.join(missing)}模型, 无法解析文档; "
            "请先在模型管理中绑定或由管理员配置默认公共模型"
        )
    # 经统一任务队列创建并投递(worker 从库读参数, 以创建者绑定模型执行)
    task = await task_service.create(
        TaskQueueCreate(
            name=f"解析文档: {doc_info.name}",
            task_type="rag_document_parse",
            payload={"document_id": document_id},
        ),
        current_user_id,
    )
    return {
        "message": "解析任务已提交至后台队列",
        "document_id": document_id,
        "task_id": task.id,
    }



# 注册路由
module_app.include_router(router, prefix="/project-documents", tags=["项目文档管理"])
