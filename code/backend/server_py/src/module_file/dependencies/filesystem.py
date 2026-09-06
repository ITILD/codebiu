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
from module_file.service.filesystem import FileService
from module_authorization.dependencies.auth import get_current_user_id_optional
from module_authorization.dependencies.permission import enforce_permission


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


async def get_download_user_id(
    entry_id: str,
    current_user_id: str | None = Depends(get_current_user_id_optional),
    file_entry_dao: FileEntryDao = Depends(get_file_entry_dao),
) -> str | None:
    """下载鉴权依赖: 已登录用户走常规权限校验; 匿名仅放行 avatar 来源条目(头像等公开资源)"""
    if current_user_id:
        await enforce_permission(current_user_id, "main", "file", "read")
        return current_user_id
    entry = await file_entry_dao.get(entry_id)
    if entry and entry.source_module == "avatar":
        return None
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录或无下载权限"
    )
