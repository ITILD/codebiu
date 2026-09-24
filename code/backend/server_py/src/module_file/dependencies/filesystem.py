"""统一文件服务依赖注入

新业务模块接入文件服务约定(知识库/头像即按此模式实现, 零自建存储):
1. 控制器/服务注入 get_file_service(本文件) —— 存储后端(local/s3/rustfs)由
   config.dev.yaml file_system.storage_type 决定, 业务代码与前端均无感;
2. 首次使用时 ensure_module_root(key, label) 幂等创建模块根目录(虚拟目录树中
   独立成模块大文件夹, source_module=key 标记来源), 再 ensure_folder 建业务子目录;
3. 小文件走 upload_file/upload_content_bytes(SHA-256去重), 大文件走
   init_multipart_session 分片链路(direct=预签名直传S3/proxy=服务端中转自动分流);
4. 条目 source_module 自动从父目录继承, 文件管理页可见但只读(get_managed_file_service
   拦截写操作), 业务操作只能经本模块接口; 前端上传复用 common/utils/storageUpload.ts
   的 createStorageUploader 适配器工厂。
"""
from fastapi import Depends, HTTPException, status

from module_file.dao.file_entry_dao import FileEntryDao
from module_file.dao.file_content_dao import FileContentDao
from module_file.do.filesystem import FileEntry
from module_file.service.filesystem import FileService
from module_file.config.download_grant import get_download_grant
from module_authorization.dependencies.auth import get_current_user_id_optional
from module_authorization.dependencies.permission import check_permission


async def get_file_entry_dao() -> FileEntryDao:
    """文件条目DAO工厂"""
    return FileEntryDao()


async def get_file_content_dao() -> FileContentDao:
    """文件内容数据访问对象DAO工厂"""
    return FileContentDao()


# 新增的依赖项工厂函数
async def get_file_service(
    file_entry_dao: FileEntryDao = Depends(get_file_entry_dao),
    file_content_dao: FileContentDao = Depends(get_file_content_dao),
) -> FileService:
    """Service工厂(业务模块注入用: rag/avatar等可自由管理自己的条目)"""
    return FileService(file_entry_dao, file_content_dao)


async def get_managed_file_service(
    file_entry_dao: FileEntryDao = Depends(get_file_entry_dao),
    file_content_dao: FileContentDao = Depends(get_file_content_dao),
) -> FileService:
    """带业务条目只读拦截的Service工厂(仅文件管理模块使用:
    source_module 标记的 rag/avatar 等业务条目禁止在文件管理中变更)"""
    return FileService(
        file_entry_dao, file_content_dao, strict_business_guard=True
    )


async def can_download_entry(user_id: str | None, entry: FileEntry) -> bool:
    """判断用户对条目是否有下载权限(不抛异常, 下载鉴权与批量探测共用)

    判定顺序:
    1. 目录条目不可下载;
    2. avatar 来源为公开资源(头像等), 匿名亦可下载;
    3. 登录用户持独立下载权限 main:file:download(全局 admin 角色穿透,
       其余角色由管理员在权限配置中单独勾选);
    4. 业务条目(source_module 标记)交由来源模块注册的授权钩子判定
       (rag: 项目 editor 及以上档位放行, 见 module_rag 注册处)。
    :param user_id: 当前用户ID(匿名为 None)
    :param entry: 文件条目
    :return: 是否放行下载
    """
    if entry.is_directory:
        return False
    if entry.source_module == "avatar":
        return True
    if user_id is None:
        return False
    if await check_permission(user_id, "main", "file", "download"):
        return True
    if entry.source_module and entry.source_module != "file":
        grant = get_download_grant(entry.source_module)
        if grant is not None and await grant(user_id, entry):
            return True
    return False


async def get_download_user_id(
    entry_id: str,
    current_user_id: str | None = Depends(get_current_user_id_optional),
    file_entry_dao: FileEntryDao = Depends(get_file_entry_dao),
) -> str | None:
    """下载鉴权依赖(见 can_download_entry 判定口径)
    - 匿名: 仅放行 avatar 来源公开条目, 其余 401
    - 已登录无权限: 403(与未登录区分, 供前端提示)
    """
    entry = await file_entry_dao.get(entry_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="文件或目录不存在"
        )
    if await can_download_entry(current_user_id, entry):
        return current_user_id
    if current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无下载权限"
        )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录或无下载权限"
    )
