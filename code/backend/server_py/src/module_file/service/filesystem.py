# self
from common.utils.db.schema.pagination import (
    InfiniteScrollParams,
    InfiniteScrollResponse,
    PaginationParams,
    PaginationResponse,
)
from module_file.do.filesystem import (
    FileEntry,
    FileEntryCreate,
    FileEntryUpdate,
    GeneratePresignedUrlRequest,
    PresignedUploadParams,
    PresignedDownloadParams,
    GeneratePresignedUploadResponse,
    GeneratePresignedDownloadResponse,
)
from module_file.dao.file_entry_dao import FileEntryDao
from module_file.dao.file_content_dao import FileContentDao
from module_file.utils.multi_storage.do.storage_config import StorageType
from module_file.config.filesystem import storage, storage_config
import hashlib
from fastapi import UploadFile, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from common.config.db import DaoRel
from pathlib import Path
from module_file.do.filesystem import FileContentCreate
import logging
from module_file.utils.multi_storage.do.storage_config import PresignedType
from common.config.index import conf
from datetime import datetime
from common.enum.task import TaskStatus

# 配置日志
logger = logging.getLogger(__name__)


class FileService:
    """文件服务类，提供虚拟文件系统的上传、下载、目录管理等功能"""

    def __init__(
        self,
        file_entry_dao: FileEntryDao | None = None,
        file_content_dao: FileContentDao | None = None,
        storage_interface=None,
    ):
        """
        初始化文件服务
        :param file_entry_dao: 文件数据访问对象，可选
        :param storage_interface: 存储接口实现，可选
        """
        self.file_entry_dao = file_entry_dao or FileEntryDao()
        self.file_content_dao = file_content_dao or FileContentDao()
        self.storage = storage_interface or storage

    async def _release_content(
        self, content_hash: str | None, session: AsyncSession
    ) -> None:
        """
        释放文件内容引用(计数-1,归零时清理物理文件与内容记录)
        :param content_hash: 内容哈希
        :param session: 数据库会话
        """
        if not content_hash:
            return
        await self.file_content_dao.ref_count_change(content_hash, -1, session)
        file_content = await self.file_content_dao.get_by_content_hash(
            content_hash, session
        )
        if file_content and file_content.ref_count <= 0:
            # 引用归零: 清理物理文件与内容记录(失败仅告警,可由后台任务兜底)
            try:
                await self.storage.delete(file_content.physical_storage)
            except Exception as e:
                logger.warning(f"清理物理文件失败(可由后台任务重试): {e}")
            await self.file_content_dao.delete(content_hash, session)

    @DaoRel
    async def delete_file(
        self, entry_id: str, session: AsyncSession | None = None
    ):
        """
        删除文件记录(逻辑删除条目,释放内容引用)
        :param entry_id: 文件条目ID
        """
        entry = await self.file_entry_dao.get(entry_id, session)
        if not entry or not entry.is_active:
            raise ValueError(f"未找到ID为 {entry_id} 的文件")
        if entry.is_directory:
            raise ValueError("目录请使用目录删除接口")
        await self.file_entry_dao.soft_delete(entry_id, session)
        await self._release_content(entry.content_hash, session)

    @DaoRel
    async def delete_folder(
        self, folder_id: str, session: AsyncSession | None = None
    ):
        """
        递归删除目录及其全部子项(虚拟文件系统)
        :param folder_id: 目录ID
        """
        try:
            # 递归 CTE 获取子树全部条目ID(含目录自身)
            subtree_ids = await self.file_entry_dao.get_subtree_ids(
                folder_id, session
            )
            if not subtree_ids:
                raise ValueError(f"未找到ID为 {folder_id} 的目录")
            # 批量逻辑删除
            await self.file_entry_dao.batch_soft_delete(subtree_ids, session)
            # 对子树中的文件统一释放内容引用(哈希已去重)
            content_hashes = await self.file_entry_dao.get_content_hashes_by_ids(
                subtree_ids, session
            )
            for content_hash in content_hashes:
                await self._release_content(content_hash, session)
        except Exception as e:
            logger.error(f"删除目录时发生错误: {e}")
            raise

    @DaoRel
    async def update(
        self,
        file_id: str,
        file_update: FileEntryUpdate,
        session: AsyncSession | None = None,
    ) -> FileEntry:
        """
        更新条目信息(名称变更自动委托重命名逻辑,保证路径一致)
        :param file_id: 条目ID
        :param file_update: 更新数据(name/description)
        :return: 更新后的条目信息
        :raises: ValueError 如果条目不存在
        """
        entry = await self.file_entry_dao.get(file_id, session)
        if not entry or not entry.is_active:
            raise ValueError("条目不存在或已被删除")
        # 拆分更新数据(路径字段不对外暴露,仅内部方法维护)
        data = file_update.model_dump(exclude_unset=True)
        new_name = data.get("name")
        new_description = data.get("description")
        # 名称变更走重命名(维护子树路径一致性,同一事务)
        if new_name and new_name != entry.name:
            entry = await self.rename(file_id, new_name, session=session)
        if new_description is not None and new_description != entry.description:
            await self.file_entry_dao.update(
                file_id, FileEntryUpdate(description=new_description), session
            )
        return await self.file_entry_dao.get(file_id, session)

    @DaoRel
    async def rename(
        self, entry_id: str, new_name: str, session: AsyncSession | None = None
    ) -> FileEntry:
        """
        重命名条目(目录重命名时同步更新子树逻辑路径)
        :param entry_id: 条目ID
        :param new_name: 新名称
        :return: 更新后的条目信息
        :raises: ValueError 如果条目不存在或同名冲突
        """
        entry = await self.file_entry_dao.get(entry_id, session)
        if not entry or not entry.is_active:
            raise ValueError("条目不存在或已被删除")
        new_name = new_name.strip()
        if not new_name:
            raise ValueError("名称不能为空")
        if entry.name == new_name:
            return entry
        # 同目录重名校验(排除自身)
        if await self.file_entry_dao.exists_by_pid_name(
            entry.pid, new_name, exclude_id=entry_id, session=session
        ):
            raise ValueError(f"当前目录下已存在同名条目: {new_name}")
        old_path = entry.logical_path
        parent_path = old_path.rsplit("/", 1)[0]
        new_path = f"{parent_path}/{new_name}"
        await self.file_entry_dao.update(
            entry_id, FileEntryUpdate(name=new_name, logical_path=new_path), session
        )
        # 目录: 子孙逻辑路径前缀同步替换
        if entry.is_directory:
            await self.file_entry_dao.update_children_path_prefix(
                old_path, new_path, session
            )
        return await self.file_entry_dao.get(entry_id, session)

    @DaoRel
    async def move(
        self,
        entry_id: str,
        target_pid: str | None,
        session: AsyncSession | None = None,
    ) -> FileEntry:
        """
        移动条目到目标目录(目录移动时同步更新子树逻辑路径)
        :param entry_id: 条目ID
        :param target_pid: 目标父目录ID(为空表示根目录)
        :return: 更新后的条目信息
        :raises: ValueError 如果条目/目标目录无效或产生环形引用
        """
        entry = await self.file_entry_dao.get(entry_id, session)
        if not entry or not entry.is_active:
            raise ValueError("条目不存在或已被删除")
        target_pid = target_pid or None
        if target_pid:
            target = await self.file_entry_dao.get(target_pid, session)
            if not target or not target.is_active:
                raise ValueError("目标目录不存在或已被删除")
            if not target.is_directory:
                raise ValueError("目标条目不是目录")
            # 环形引用防护: 目标不能是自身或自身的子孙目录
            if target.logical_path == entry.logical_path or target.logical_path.startswith(
                entry.logical_path + "/"
            ):
                raise ValueError("不能移动到自身或其子目录下")
            new_path = f"{target.logical_path.rstrip('/')}/{entry.name}"
        else:
            new_path = f"/{entry.name}"
        # 位置未变化直接返回
        if new_path == entry.logical_path and target_pid == (entry.pid or None):
            return entry
        # 目标目录同名冲突校验(排除自身)
        if await self.file_entry_dao.exists_by_pid_name(
            target_pid, entry.name, exclude_id=entry_id, session=session
        ):
            raise ValueError(f"目标目录下已存在同名条目: {entry.name}")
        old_path = entry.logical_path
        await self.file_entry_dao.update(
            entry_id, FileEntryUpdate(pid=target_pid, logical_path=new_path), session
        )
        # 目录: 子孙逻辑路径前缀同步替换
        if entry.is_directory:
            await self.file_entry_dao.update_children_path_prefix(
                old_path, new_path, session
            )
        return await self.file_entry_dao.get(entry_id, session)

    async def get_file_entry(self, id: str) -> FileEntry | None:
        """
        获取文件或目录信息
        :param id: 文件或目录的ID
        :return: 文件或目录信息对象，不存在返回None
        """
        return await self.file_entry_dao.get(id)

    async def list_all(self, pagination: PaginationParams) -> PaginationResponse:
        """
        分页查询所有条目
        :param pagination: 分页参数
        :return: 分页响应结果
        """
        items = await self.file_entry_dao.list_all(pagination)
        total = await self.file_entry_dao.count()
        return PaginationResponse.create(items, total, pagination)

    async def list_by_pid(
        self,
        pid: str | None,
        pagination: PaginationParams,
        name: str | None = None,
    ) -> PaginationResponse:
        """
        分页查询指定目录下的条目(虚拟文件系统目录浏览)
        :param pid: 父目录ID(为空表示根目录)
        :param pagination: 分页参数
        :param name: 名称模糊过滤(为空不过滤)
        :return: 分页响应结果(目录排前,名称排序)
        """
        items = await self.file_entry_dao.list_by_pid(pid, pagination, name)
        total = await self.file_entry_dao.count_by_pid(pid, name)
        return PaginationResponse.create(items, total, pagination)

    async def list_dirs(self, pid: str | None) -> list[FileEntry]:
        """
        查询指定目录下的全部子目录(目录树选择用)
        :param pid: 父目录ID(为空表示根目录)
        :return: 子目录列表
        """
        return await self.file_entry_dao.list_dirs_by_pid(pid)

    @DaoRel
    async def create_folder(
        self,
        name: str,
        pid: str | None = None,
        owner_user_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> FileEntry:
        """
        创建目录(虚拟文件系统)
        :param name: 目录名称
        :param pid: 父目录ID(为空表示根目录)
        :param owner_user_id: 拥有者用户ID
        :return: 新创建的目录信息
        :raises: ValueError 如果父目录不存在或同名条目已存在
        """
        # 校验父目录存在且为目录
        if pid:
            parent = await self.file_entry_dao.get(pid, session)
            if not parent or not parent.is_active:
                raise ValueError("父目录不存在或已被删除")
            if not parent.is_directory:
                raise ValueError("父级条目不是目录")
            logical_path = f"{parent.logical_path.rstrip('/')}/{name}"
        else:
            logical_path = f"/{name}"

        # 同目录下名称唯一校验
        if await self.file_entry_dao.exists_by_pid_name(pid, name, session=session):
            raise ValueError(f"当前目录下已存在同名条目: {name}")

        folder = FileEntryCreate(
            name=name,
            pid=pid,
            logical_path=logical_path,
            is_directory=True,
            user_id=owner_user_id,
        )
        folder_id = await self.file_entry_dao.add(folder, session)
        return await self.file_entry_dao.get(folder_id, session)

    async def get_scroll(self, params: InfiniteScrollParams) -> InfiniteScrollResponse:
        """
        滚动加载文件列表
        :param params: 滚动参数
        :return: 滚动响应结果
        """
        items: list = await self.file_entry_dao.get_scroll(params)
        return InfiniteScrollResponse.create(items, params.limit)

    ####################################通用上传/下载(本地/对象存储由配置切换)##############################################
    @DaoRel
    async def upload_file(
        self,
        file: UploadFile,
        description: str = None,
        pid: str = None,
        owner_user_id: str = None,
        session: AsyncSession | None = None,
    ) -> FileEntry:
        """
        上传文件到指定目录(虚拟文件系统)
        基于内容哈希(SHA-256)去重: 相同内容秒传,不重复占用物理存储
        :param file: 上传的文件对象
        :param description: 文件描述
        :param pid: 父目录ID(为空表示根目录)
        :param owner_user_id: 上传者ID
        :return: 文件信息对象
        :raises: ValueError 父目录无效/同名冲突/大小或类型超限
        """
        # 校验父目录
        if pid:
            parent = await self.file_entry_dao.get(pid, session)
            if not parent or not parent.is_active:
                raise ValueError("父目录不存在或已被删除")
            if not parent.is_directory:
                raise ValueError("父级条目不是目录")
            dir_path = parent.logical_path.rstrip("/")
        else:
            dir_path = ""

        content = await file.read()
        # 大小与MIME类型校验(依据 file_system 配置)
        if len(content) > storage_config.max_size_bytes:
            raise ValueError(
                f"文件大小超过限制: {storage_config.max_size}MB"
            )
        mime_type = file.content_type or "application/octet-stream"
        if not storage_config.is_mime_allowed(mime_type):
            raise ValueError(f"不支持的文件类型: {mime_type}")

        # 同目录同名冲突校验
        if await self.file_entry_dao.exists_by_pid_name(
            pid, file.filename, session=session
        ):
            raise ValueError(f"当前目录下已存在同名文件: {file.filename}")

        # 内容哈希去重: 已存在且完成的内容直接复用(秒传)
        content_hash = hashlib.sha256(content).hexdigest()
        file_content = await self.file_content_dao.get_by_content_hash(
            content_hash, session
        )
        file_ext = Path(file.filename).suffix
        if file_content and file_content.content_status == TaskStatus.SUCCESS:
            physical_storage = file_content.physical_storage
        else:
            # 新内容或上次上传中断: 覆盖写入物理存储(哈希命名,日期分目录)
            date_str = datetime.now().strftime("%Y%m%d")
            physical_storage = f"uploads/{date_str}/{content_hash}{file_ext}"
            await self.storage.save(physical_storage, content)
            if not file_content:
                await self.file_content_dao.add(
                    FileContentCreate(
                        content_hash=content_hash,
                        physical_storage=physical_storage,
                        file_size_bytes=len(content),
                        storage_type=conf.file_system.storage_type,
                    ),
                    session,
                )

        # 建立虚拟文件系统条目
        file_create = FileEntryCreate(
            name=file.filename,
            pid=pid,
            logical_path=f"{dir_path}/{file.filename}",
            file_size_bytes=len(content),
            file_extension=file_ext[1:] if file_ext else "",
            mime_type=mime_type,
            content_hash=content_hash,
            description=description,
            user_id=owner_user_id,
            is_active=True,
        )
        created_id = await self.file_entry_dao.add(file_create, session)
        # 引用计数+1(首传时同时将内容状态置为SUCCESS)
        await self.file_content_dao.ref_count_change(content_hash, 1, session)
        logger.info(f"文件上传成功: {file_create.name} -> {file_create.logical_path}")
        return await self.file_entry_dao.get(created_id, session)

    async def get_file_info_for_download(
        self, entry_id: str
    ) -> tuple[str, str, str]:
        """
        获取文件下载所需的信息
        :param entry_id: 文件条目ID
        :return: (文件名, MIME类型, 物理存储键)
        """
        try:
            # 联查条目与内容元数据(物理存储键位于内容表)
            entry_with_content = await self.file_entry_dao.get_file_entry_with_content(
                entry_id
            )
            if not entry_with_content or not entry_with_content.is_active:
                logger.warning(f"文件不存在或已被禁用: {entry_id}")
                raise HTTPException(status_code=404, detail="文件不存在或已被禁用")
            if entry_with_content.is_directory:
                raise HTTPException(status_code=400, detail="目录不支持下载")
            if not entry_with_content.physical_storage:
                raise HTTPException(status_code=404, detail="文件内容记录缺失")

            # 使用存储接口检查物理文件是否存在
            file_exists = await self.storage.exists(entry_with_content.physical_storage)
            if not file_exists:
                logger.error(f"物理文件不存在: {entry_with_content.physical_storage}")
                raise HTTPException(status_code=404, detail="物理文件不存在")

            return (
                entry_with_content.name,
                entry_with_content.mime_type,
                entry_with_content.physical_storage,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取文件信息时发生错误: {e}")
            raise HTTPException(status_code=500, detail=f"获取文件信息时发生错误: {e}")

    async def stream_file_content(self, file_path: str, chunk_size: int = 8192):
        """
        流式读取文件内容(分块加载,避免大文件全量载入内存)
        :param file_path: 物理存储键
        :param chunk_size: 每次读取的块大小
        :yield: 文件内容块
        """
        try:
            async for chunk in self.storage.iter_chunks(file_path, chunk_size):
                yield chunk
        except Exception as e:
            logger.error(f"读取文件内容时发生错误: {e}")
            raise

    ######################################兼容本地存储和s3/minio/oss/rustfs对象存储######################################
    @DaoRel
    async def generate_presigned_url_upload(
        self,
        presigned_url_request: GeneratePresignedUrlRequest,
        presigned_url_path: str,
        session: AsyncSession | None = None,
    ) -> GeneratePresignedUploadResponse:
        """
        生成用于上传文件的预签名 URL。

        若文件内容已存在且状态为 SUCCESS，则不生成新 URL；
        否则（新文件或上传未完成），生成预签名上传地址。
        本地存储时，URL 会拼接为完整路径。
        """
        if presigned_url_request.file_size_bytes > storage_config.max_size_bytes:
            raise HTTPException(status_code=400, detail="文件大小超过限制")

        # 检查文件是否已存在(通过sha256)
        content_hash = presigned_url_request.content_hash
        existing_file = await self.file_content_dao.get_by_content_hash(content_hash)

        if existing_file:
            physical_storage = existing_file.physical_storage
            content_status = existing_file.content_status
            logger.info(f"文件已存在: {content_hash}")
        else:
            # 新内容：生成唯一物理路径
            date_str = datetime.now().strftime("%Y%m%d")
            ext = Path(presigned_url_request.filename).suffix
            file_name = f"{content_hash}{ext}"
            physical_storage = f"{presigned_url_request.domain}/{date_str}/{file_name}"

            # 考虑事务,后续预签名成功再添加
            file_content_create = FileContentCreate(
                content_hash=content_hash,
                physical_storage=physical_storage,
                file_size_bytes=presigned_url_request.file_size_bytes,
                storage_type=conf.file_system.storage_type,
            )
            await self.file_content_dao.add(file_content_create, session)

            content_status = file_content_create.content_status

        # 上传未完成要生成预签名 URL(包括新文件)
        presigned_url = None
        if content_status != TaskStatus.SUCCESS:
            presigned_url = await self.storage.generate_presigned_url(
                PresignedType.PUT,
                physical_storage,
                presigned_url_request.content_type,
            )
            if conf.file_system.storage_type == StorageType.LOCAL:
                base_path = presigned_url_path.replace("generate_", "")
                presigned_url = f"{base_path}{presigned_url}"

        return GeneratePresignedUploadResponse(
            presigned_url=presigned_url,
            is_existing_file=bool(existing_file),
            content_status=content_status,
        )

    async def presigned_url_upload(
        self,
        file_path: str,
        presigned_upload_params: PresignedUploadParams,
        content: bytes,
    ) -> bool:
        """
        使用预签名URL上传数据
        :param presigned_url: 预签名URL
        :param data: 要上传的数据
        :return: 是否上传成功
        """
        try:
            success = await self.storage.upload_with_presigned_url(
                file_path, presigned_upload_params, content
            )
            return success
        except Exception as e:
            logger.error(f"使用预签名URL上传时发生错误: {e}")
            raise

    @DaoRel
    async def presigned_url_upload_success(
        self,
        file: FileEntryCreate,
        session: AsyncSession | None = None,
    ):
        # 文件夹文件业务逻辑
        file_id = await self.file_entry_dao.add(file, session)
        # 文件内容 引用计数+1,更新状态为成功
        await self.file_content_dao.ref_count_change(file.content_hash, 1, session)
        return file_id

    async def generate_presigned_url_download(
        self,
        file_id: str,
        presigned_url_path: str,
    ) -> GeneratePresignedDownloadResponse:
        """
        生成预签名URL用于下载文件
        :param file_id: 文件ID
        :return: 预签名URL或None
        """
        try:
            file_entry_with_content = (
                await self.file_entry_dao.get_file_entry_with_content(file_id)
            )

            # 生成预签名URL，使用文件的physical_storage作为key
            presigned_url = await self.storage.generate_presigned_url(
                PresignedType.GET, file_entry_with_content.physical_storage
            )

            # 判断存储类型
            if conf.file_system.storage_type == StorageType.LOCAL:
                base_path = presigned_url_path.replace("generate_", "")
                presigned_url = f"{base_path}{presigned_url}"

            return GeneratePresignedDownloadResponse(
                presigned_url=presigned_url,
            )
        except Exception as e:
            logger.error(f"生成预签名下载URL时发生错误: {e}")
            raise

    async def presigned_url_download(
        self, file_path: str, presigned_download_params: PresignedDownloadParams
    ) -> bytes:
        """
        预签名URL用于下载文件
        :param file_content_id: 文件ID
        :return: 预签名URL或None
        """
        try:
            # 获取文件内容
            content = await self.storage.download_with_presigned_url(
                file_path,
                presigned_download_params,
            )
            return content
        except Exception as e:
            logger.error(f"生成预签名下载URL时发生错误: {e}")
            raise
