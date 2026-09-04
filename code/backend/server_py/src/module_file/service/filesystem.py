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
    FileEntryWithContent,
    FileContentCreate,
    GeneratePresignedUrlRequest,
    PresignedUploadParams,
    PresignedDownloadParams,
    GeneratePresignedUploadResponse,
    GeneratePresignedDownloadResponse,
    StorageStats,
    MigrateRequest,
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
import logging
from module_file.utils.multi_storage.do.storage_config import PresignedType
from common.config.index import conf
from common.config.path import DIR_UPLOAD
from datetime import datetime
from common.enum.task import TaskStatus

# 配置日志
logger = logging.getLogger(__name__)


def build_storage(storage_type: StorageType | str):
    """
    按类型构建存储实例(存储迁移/双存储搬运用,与全局单例互不影响)
    :param storage_type: 存储类型(local/s3/rustfs)
    :return: StorageInterface 实例
    """
    from module_file.utils.multi_storage.do.storage_config import (
        StorageConfigFactory,
    )
    from module_file.utils.multi_storage.storage_factory import StorageFactory

    cfg = StorageConfigFactory.create(str(storage_type), conf.file_system)
    # local 未配置目录时回退到全局上传目录(与 config/filesystem.py 保持一致)
    if str(storage_type) == StorageType.LOCAL and not getattr(cfg, "base_dir", None):
        cfg.base_dir = str(DIR_UPLOAD)
    return StorageFactory.create(cfg)


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

    async def list_paged(self, pagination: PaginationParams) -> PaginationResponse:
        """
        分页查询所有条目
        :param pagination: 分页参数
        :return: 分页响应结果
        """
        items = await self.file_entry_dao.list_paged(pagination)
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
    async def _upload_content(
        self,
        content: bytes,
        filename: str,
        description: str | None = None,
        pid: str | None = None,
        owner_user_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> FileEntry:
        """
        字节级上传核心逻辑(虚拟文件系统,UploadFile/客户端直传共用)
        基于内容哈希(SHA-256)去重: 相同内容秒传,不重复占用物理存储
        :param content: 文件字节内容
        :param filename: 文件名
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

        # 大小与MIME类型校验(依据 file_system 配置)
        if len(content) > storage_config.max_size_bytes:
            raise ValueError(
                f"文件大小超过限制: {storage_config.max_size}MB"
            )
        mime_type = self._guess_mime(filename) or "application/octet-stream"
        if not storage_config.is_mime_allowed(mime_type):
            raise ValueError(f"不支持的文件类型: {mime_type}")

        # 同目录同名冲突校验
        if await self.file_entry_dao.exists_by_pid_name(
            pid, filename, session=session
        ):
            raise ValueError(f"当前目录下已存在同名文件: {filename}")

        # 内容哈希去重: 已存在且完成的内容直接复用(秒传)
        content_hash = hashlib.sha256(content).hexdigest()
        file_content = await self.file_content_dao.get_by_content_hash(
            content_hash, session
        )
        file_ext = Path(filename).suffix
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
            name=filename,
            pid=pid,
            logical_path=f"{dir_path}/{filename}",
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

    @staticmethod
    def _guess_mime(filename: str) -> str | None:
        """
        按扩展名推断MIME类型(客户端直传时无Content-Type头,保证类型校验一致)
        :param filename: 文件名
        :return: MIME类型,未知返回None
        """
        import mimetypes

        mime, _ = mimetypes.guess_type(filename)
        return mime

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
        上传文件到指定目录(虚拟文件系统,HTTP multipart入口)
        :param file: 上传的文件对象
        :param description: 文件描述
        :param pid: 父目录ID(为空表示根目录)
        :param owner_user_id: 上传者ID
        :return: 文件信息对象
        :raises: ValueError 父目录无效/同名冲突/大小或类型超限
        """
        content = await file.read()
        return await self._upload_content(
            content, file.filename, description, pid, owner_user_id, session=session
        )

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

    ####################################路径操作/搜索/复制/读取(虚拟文件系统高阶能力)##############################################

    async def get_by_path(self, logical_path: str) -> FileEntry | None:
        """
        按逻辑路径精确查询条目
        :param logical_path: 用户视角完整路径(如 /docs/readme.md)
        :return: 条目对象,不存在返回None
        """
        return await self.file_entry_dao.get_by_logical_path(logical_path)

    @DaoRel
    async def list_by_path(
        self,
        logical_path: str,
        pagination: PaginationParams,
        name: str | None = None,
        session: AsyncSession | None = None,
    ) -> PaginationResponse:
        """
        按逻辑路径浏览目录(前端路径导航用)
        :param logical_path: 目录逻辑路径
        :param pagination: 分页参数
        :param name: 名称模糊过滤
        :return: 分页响应结果
        """
        entry = await self.file_entry_dao.get_by_logical_path(
            logical_path, session
        )
        if not entry or not entry.is_directory:
            raise ValueError(f"目录不存在: {logical_path}")
        return await self.list_by_pid(entry.id, pagination, name)

    @DaoRel
    async def mkdir_p(
        self,
        path: str,
        owner_user_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> FileEntry:
        """
        按逻辑路径递归创建目录(mkdir -p 语义,已存在直接返回)
        :param path: 目录逻辑路径(如 /docs/images,支持多级一次创建)
        :param owner_user_id: 拥有者用户ID
        :return: 最终层目录条目
        :raises: ValueError 路径段非法或与同名文件冲突
        """
        # 规范化路径: 去首尾斜杠,拆分层级
        parts = [p.strip() for p in path.strip("/").split("/") if p.strip()]
        if not parts:
            raise ValueError("目录路径不能为空")
        current_pid: str | None = None
        current_path = ""
        entry: FileEntry | None = None
        for part in parts:
            # 逐级按完整逻辑路径查询(存在则复用,不存在则创建)
            current_path = f"{current_path}/{part}"
            entry = await self.file_entry_dao.get_by_logical_path(
                current_path, session
            )
            if entry is None:
                entry = await self.create_folder(
                    part, current_pid, owner_user_id, session=session
                )
            elif not entry.is_directory:
                raise ValueError(f"路径 /{part} 已被同名文件占用")
            current_pid = entry.id
        return entry

    async def search(
        self, keyword: str, pagination: PaginationParams
    ) -> PaginationResponse:
        """
        全树模糊搜索(匹配名称或逻辑路径)
        :param keyword: 搜索关键字
        :param pagination: 分页参数
        :return: 分页响应结果
        """
        items = await self.file_entry_dao.search(keyword, pagination)
        total = await self.file_entry_dao.count_search(keyword)
        return PaginationResponse.create(items, total, pagination)

    @DaoRel
    async def copy_entry(
        self,
        entry_id: str,
        target_pid: str | None = None,
        owner_user_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> FileEntry:
        """
        复制条目(文件/目录自动分发)
        文件复制: 新建条目指向同一内容哈希,物理文件不复制(引用计数+1)
        目录复制: 递归复制整棵子树(内容哈希去重,同一内容仅+1次引用)
        :param entry_id: 源条目ID
        :param target_pid: 目标父目录ID(为空表示根目录)
        :param owner_user_id: 操作者用户ID
        :return: 复制出的新条目
        """
        entry = await self.file_entry_dao.get(entry_id, session)
        if not entry or not entry.is_active:
            raise ValueError("条目不存在或已被删除")
        # 校验目标目录
        if target_pid:
            target = await self.file_entry_dao.get(target_pid, session)
            if not target or not target.is_active:
                raise ValueError("目标目录不存在或已被删除")
            if not target.is_directory:
                raise ValueError("目标条目不是目录")
            # 环形防护: 目录不能复制到自身子树内
            if entry.is_directory and (
                target.logical_path == entry.logical_path
                or target.logical_path.startswith(entry.logical_path + "/")
            ):
                raise ValueError("不能复制到自身或其子目录下")
            target_path = target.logical_path.rstrip("/")
        else:
            target_path = ""
        # 目标同名冲突校验
        if await self.file_entry_dao.exists_by_pid_name(
            target_pid, entry.name, session=session
        ):
            raise ValueError(f"目标目录下已存在同名条目: {entry.name}")
        copied = await self._copy_recursive(
            entry, target_pid, target_path, owner_user_id, session
        )
        return copied

    async def _copy_recursive(
        self,
        entry: FileEntry,
        target_pid: str | None,
        target_path: str,
        owner_user_id: str | None,
        session: AsyncSession,
    ) -> FileEntry:
        """
        递归复制单个条目及其子树(内部方法,调用方负责冲突/环形校验)
        :param entry: 源条目
        :param target_pid: 目标父目录ID
        :param target_path: 目标父目录逻辑路径(为空表示根目录)
        :param owner_user_id: 操作者用户ID
        :return: 新条目
        """
        new_path = f"{target_path}/{entry.name}" if target_path else f"/{entry.name}"
        if entry.is_directory:
            folder_id = await self.file_entry_dao.add(
                FileEntryCreate(
                    name=entry.name,
                    pid=target_pid,
                    logical_path=new_path,
                    is_directory=True,
                    description=entry.description,
                    user_id=owner_user_id or entry.user_id,
                ),
                session,
            )
            # 递归复制全部直接子项
            children = await self.file_entry_dao.list_children(entry.id, session)
            for child in children:
                await self._copy_recursive(
                    child, folder_id, new_path, owner_user_id, session
                )
            return await self.file_entry_dao.get(folder_id, session)
        # 文件: 新条目指向同一内容哈希,物理文件不复制
        file_id = await self.file_entry_dao.add(
            FileEntryCreate(
                name=entry.name,
                pid=target_pid,
                logical_path=new_path,
                is_directory=False,
                content_hash=entry.content_hash,
                file_size_bytes=entry.file_size_bytes,
                file_extension=entry.file_extension,
                mime_type=entry.mime_type,
                description=entry.description,
                user_id=owner_user_id or entry.user_id,
            ),
            session,
        )
        await self.file_content_dao.ref_count_change(entry.content_hash, 1, session)
        return await self.file_entry_dao.get(file_id, session)

    async def read_file_bytes(self, entry_id: str) -> bytes:
        """
        读取文件完整字节内容(小文件直接读,大文件请用 stream_file_content)
        :param entry_id: 文件条目ID
        :return: 文件字节内容
        :raises: ValueError 文件不存在/是目录/内容缺失
        """
        info = await self.file_entry_dao.get_file_entry_with_content(entry_id)
        if not info or not info.is_active:
            raise ValueError(f"文件不存在: {entry_id}")
        if info.is_directory:
            raise ValueError("目录不支持按内容读取")
        if not info.physical_storage:
            raise ValueError("文件内容记录缺失")
        return await self.storage.load(info.physical_storage)

    async def read_file_text(self, entry_id: str, encoding: str = "utf-8") -> str:
        """
        读取文本文件内容
        :param entry_id: 文件条目ID
        :param encoding: 文本编码(默认utf-8)
        :return: 文本内容
        """
        return (await self.read_file_bytes(entry_id)).decode(encoding)

    async def stream_entry_chunks(self, entry_id: str, chunk_size: int = 8192):
        """
        按条目ID流式读取文件内容(异步生成器,跨模块大文件转发用)
        :param entry_id: 文件条目ID
        :param chunk_size: 每次读取的块大小
        :yield: 文件内容块
        """
        info = await self.file_entry_dao.get_file_entry_with_content(entry_id)
        if not info or not info.is_active:
            raise ValueError(f"文件不存在: {entry_id}")
        if info.is_directory:
            raise ValueError("目录不支持按内容读取")
        if not info.physical_storage:
            raise ValueError("文件内容记录缺失")
        async for chunk in self.storage.iter_chunks(info.physical_storage, chunk_size):
            yield chunk

    @DaoRel
    async def get_stats(self, session: AsyncSession | None = None) -> StorageStats:
        """
        存储统计(条目数/物理内容数/总占用)
        :return: 统计信息
        """
        entry_total, file_total, folder_total = (
            await self.file_entry_dao.count_by_type(session)
        )
        content_total, used_bytes = await self.file_content_dao.stats(session)
        return StorageStats(
            storage_type=str(conf.file_system.storage_type),
            entry_total=entry_total,
            file_total=file_total,
            folder_total=folder_total,
            content_total=content_total,
            used_bytes=used_bytes,
        )

    @DaoRel
    async def migrate_storage(
        self, req: MigrateRequest, session: AsyncSession | None = None
    ) -> dict:
        """
        存储迁移: 把源存储的全部物理内容搬运到目标存储(逻辑条目与物理键不变)
        用途: 配置切换 local<->rustfs/s3 前,先迁移历史数据实现无缝切换
        :param req: MigrateRequest(from_type/to_type)
        :return: 迁移结果 {total, migrated, skipped, failed}
        """
        from module_file.do.filesystem import FileContentUpdate

        if req.from_type == req.to_type:
            raise ValueError("源与目标存储类型相同,无需迁移")
        src = build_storage(req.from_type)
        dst = build_storage(req.to_type)
        contents = await self.file_content_dao.list_all(session)
        migrated, skipped, failed = 0, 0, []
        for c in contents:
            # 已在目标存储的内容跳过(支持断点续迁)
            if c.storage_type is not None and str(c.storage_type) == str(req.to_type):
                skipped += 1
                continue
            try:
                data = await src.load(c.physical_storage)
                await dst.save(c.physical_storage, data)
                # 更新内容记录的存储类型(物理键不变)
                await self.file_content_dao.update(
                    c.content_hash,
                    FileContentUpdate(storage_type=req.to_type),
                    session,
                )
                migrated += 1
            except Exception as e:
                logger.error(f"迁移失败 {c.content_hash}: {e}")
                failed.append({"content_hash": c.content_hash, "error": str(e)})
        logger.info(
            f"存储迁移完成: {req.from_type}->{req.to_type} "
            f"migrated={migrated} skipped={skipped} failed={len(failed)}"
        )
        return {
            "total": len(contents),
            "migrated": migrated,
            "skipped": skipped,
            "failed": failed,
        }

    ######################################兼容本地存储和s3/minio/oss/rustfs对象存储######################################
    @DaoRel
    async def generate_presigned_url_upload(
        self,
        presigned_url_request: GeneratePresignedUrlRequest,
        presigned_url_path: str,
        base_url: str = "",
        session: AsyncSession | None = None,
    ) -> GeneratePresignedUploadResponse:
        """
        生成用于上传文件的预签名 URL。

        若文件内容已存在且状态为 SUCCESS，则不生成新 URL；
        否则（新文件或上传未完成），生成预签名上传地址。
        前后端接口统一: 无论 local 还是 rustfs/s3,返回的都是可直接 PUT 的完整 URL
        (local 指向后端代理端点, rustfs/s3 指向对象存储直传地址)
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
                # 本地签名是相对路径,拼接为完整URL指向后端代理端点(与对象存储直传协议一致)
                # presigned_url_path 由 controller 直接传入预签名代理端点常量,无需再派生
                presigned_url = f"{base_url}{presigned_url_path}{presigned_url}"

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
        """预签名URL上传成功后的落库处理:登记文件条目并给文件内容引用计数+1

        :param file: 文件条目创建数据
        :param session: 可选数据库会话(事务内复用)
        :return: 新建的文件条目ID
        """
        # 文件夹文件业务逻辑
        file_id = await self.file_entry_dao.add(file, session)
        # 文件内容 引用计数+1,更新状态为成功
        await self.file_content_dao.ref_count_change(file.content_hash, 1, session)
        return file_id

    async def generate_presigned_url_download(
        self,
        file_id: str,
        presigned_url_path: str,
        base_url: str = "",
    ) -> GeneratePresignedDownloadResponse:
        """
        生成预签名URL用于下载文件
        前后端接口统一: local 返回后端代理完整URL, rustfs/s3 返回对象存储直传URL
        :param file_id: 文件ID
        :param presigned_url_path: 预签名下载代理端点路径
        :param base_url: 服务端根地址(scheme://host:port,用于拼接本地完整URL)
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
                # presigned_url_path 由 controller 直接传入预签名代理端点常量,无需再派生
                presigned_url = f"{base_url}{presigned_url_path}{presigned_url}"

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
