# self
from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_file.do.filesystem import (
    FileEntry,
    FileEntryCreate,
    FileEntryUpdate,
    FileEntryWithContent,
    FileContentCreate,
    FileContentUpdate,
    MultipartInitRequest,
    MultipartInitResponse,
    MultipartCompleteRequest,
    MultipartPartInfo,
    EntryCreateRequest,
    UploadModeResponse,
    StorageStats,
    MigrateRequest,
)
from module_file.dao.file_entry_dao import FileEntryDao
from module_file.dao.file_content_dao import FileContentDao
from module_file.utils.multi_storage.do.storage_config import StorageType
from module_file.config.filesystem import storage, storage_config
import base64
import hashlib
import hmac
import json
import time
import uuid
from fastapi import UploadFile, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from common.config.db import DaoRel
from pathlib import Path
import logging
from common.config.index import conf
from common.config.path import DIR_UPLOAD
from datetime import datetime
from common.enum.task import TaskStatus

# 配置日志
logger = logging.getLogger(__name__)

# 分片上传参数
MULTIPART_PART_SIZE = 8 * 1024 * 1024  # 单片大小 8MB
_MULTIPART_TOKEN_TTL = 24 * 3600  # 分片会话凭证有效期 24h
_PRESIGN_EXPIRES = 3600  # 预签名URL有效期 1h


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

    ####################################通用上传/下载(本地/对象存储由配置切换)##############################################
    async def _validate_parent_dir(
        self, pid: str | None, session: AsyncSession | None
    ) -> str:
        """
        校验父目录有效性,返回其逻辑路径(根目录返回空串,上传/秒传/分片共用)
        :param pid: 父目录ID
        :param session: 数据库会话
        :return: 父目录逻辑路径(已去尾部斜杠)
        """
        if not pid:
            return ""
        parent = await self.file_entry_dao.get(pid, session)
        if not parent or not parent.is_active:
            raise ValueError("父目录不存在或已被删除")
        if not parent.is_directory:
            raise ValueError("父级条目不是目录")
        return parent.logical_path.rstrip("/")

    async def _create_entry_from_content(
        self,
        name: str,
        pid: str | None,
        dir_path: str,
        content_hash: str,
        file_size_bytes: int,
        mime_type: str | None,
        description: str | None,
        owner_user_id: str | None,
        session: AsyncSession | None,
    ) -> FileEntry:
        """
        基于已完成的内容记录创建虚拟文件条目(直传/分片/秒传共用收尾逻辑)
        :return: 新建的文件条目
        """
        file_ext = Path(name).suffix
        file_create = FileEntryCreate(
            name=name,
            pid=pid,
            logical_path=f"{dir_path}/{name}",
            file_size_bytes=file_size_bytes,
            file_extension=file_ext[1:] if file_ext else "",
            mime_type=mime_type or "application/octet-stream",
            content_hash=content_hash,
            description=description,
            user_id=owner_user_id,
            is_active=True,
        )
        created_id = await self.file_entry_dao.add(file_create, session)
        # 引用计数+1(同时将内容状态置为SUCCESS)
        await self.file_content_dao.ref_count_change(content_hash, 1, session)
        logger.info(f"文件上传成功: {name} -> {file_create.logical_path}")
        return await self.file_entry_dao.get(created_id, session)

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
        字节级上传核心逻辑(小文件直传,大文件请走分片上传)
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
        dir_path = await self._validate_parent_dir(pid, session)

        # 大小与MIME类型校验(依据 file_system 配置,直传仅服务小文件)
        if len(content) > storage_config.max_size_bytes:
            raise ValueError(
                f"文件大小超过直传限制: {storage_config.max_size}MB, 请使用分片上传"
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

        return await self._create_entry_from_content(
            filename, pid, dir_path, content_hash, len(content),
            mime_type, description, owner_user_id, session,
        )

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
        上传文件到指定目录(小文件直传入口,超过 max_size 请走分片上传)
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

    ####################################分片上传(multipart,大文件)##############################################
    # 会话凭证 token: base64url(json) + HMAC-SHA256 签名,自包含物理键/S3会话ID/上传模式,无状态可跨请求传递

    @staticmethod
    def _multipart_sign(payload: str) -> str:
        """对分片会话凭证载荷计算HMAC-SHA256签名"""
        return hmac.new(
            conf.token.secret_key.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()

    def _supports_presign(self) -> bool:
        """当前存储是否支持预签名直传(S3协议存储支持,本地磁盘必须中转)"""
        from module_file.utils.multi_storage.session.impl.storage_s3 import (
            S3StorageInterface,
        )

        return isinstance(self.storage, S3StorageInterface)

    @staticmethod
    def _make_multipart_token(
        key: str, upload_id: str, content_hash: str, mode: str
    ) -> str:
        """
        生成分片上传会话凭证(签名token,防伪造/防路径穿越)
        :param key: 物理存储键(临时键,完成时归位到哈希键)
        :param upload_id: 存储侧分片会话ID(S3 UploadId / local 会话目录名)
        :param content_hash: 前端声称的内容SHA-256(init 请求携带,秒传判断与完成归位依据)
        :param mode: 上传模式 direct=预签名直传 / proxy=服务端中转
        """
        payload = (
            base64.urlsafe_b64encode(
                json.dumps(
                    {
                        "key": key,
                        "uid": upload_id,
                        "hash": content_hash,
                        "mode": mode,
                        "exp": int(time.time()) + _MULTIPART_TOKEN_TTL,
                    },
                    separators=(",", ":"),
                ).encode()
            )
            .decode()
            .rstrip("=")
        )
        return f"{payload}.{FileService._multipart_sign(payload)}"

    @staticmethod
    def _parse_multipart_token(token: str) -> dict:
        """
        解析并校验分片上传会话凭证
        :return: {"key": 物理键, "uid": 存储会话ID, "hash": 前端SHA-256, "mode": 上传模式}
        :raises: ValueError 凭证非法/过期
        """
        try:
            payload, sig = token.rsplit(".", 1)
        except ValueError:
            raise ValueError("非法的分片上传凭证")
        if not hmac.compare_digest(sig, FileService._multipart_sign(payload)):
            raise ValueError("非法的分片上传凭证")
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if time.time() > data.get("exp", 0):
            raise ValueError("分片上传会话已过期,请重新上传")
        return data

    @DaoRel
    async def init_multipart_upload(
        self,
        req: MultipartInitRequest,
        owner_user_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> MultipartInitResponse:
        """
        初始化上传(秒传/去重/校验都在此凭证签发阶段完成,数据面直传不经服务端)
        :param req: 初始化请求(文件名/大小/SHA-256/父目录)
        :param owner_user_id: 上传者ID
        :return: 会话凭证、分片大小与上传模式
                 - is_existing=True: 秒传,直接调 /upload-complete 建条目
                 - mode=direct: part_urls 携带每片预签名URL,前端直传S3
                 - mode=proxy: 前端经服务端中转上传分片(local 存储)
        """
        # ===== 校验阶段(get 凭证时完成) =====
        dir_path = await self._validate_parent_dir(req.pid, session)
        if await self.file_entry_dao.exists_by_pid_name(
            req.pid, req.filename, session=session
        ):
            raise ValueError(f"当前目录下已存在同名文件: {req.filename}")
        mime_type = self._guess_mime(req.filename) or req.content_type or "application/octet-stream"
        if not storage_config.is_mime_allowed(mime_type):
            raise ValueError(f"不支持的文件类型: {mime_type}")

        # ===== 秒传判断: 相同内容已完成上传,直接建条目即可 =====
        existing = await self.file_content_dao.get_by_content_hash(
            req.content_hash, session
        )
        if existing and existing.content_status == TaskStatus.SUCCESS:
            return MultipartInitResponse(is_existing=True, part_size=MULTIPART_PART_SIZE)

        # 内容记录: 直接以前端SHA-256建PENDING记录(复用未完成记录;完成时按存储侧归位结果校正)
        if existing:
            physical_key = existing.physical_storage
        else:
            physical_key = (
                f"uploads/{datetime.now().strftime('%Y%m%d')}/{uuid.uuid4().hex}"
                f"{Path(req.filename).suffix}"
            )
            await self.file_content_dao.add(
                FileContentCreate(
                    content_hash=req.content_hash,
                    physical_storage=physical_key,
                    file_size_bytes=req.file_size_bytes,
                    storage_type=conf.file_system.storage_type,
                ),
                session,
            )

        # ===== 凭证签发阶段: 按存储能力决定 direct(直传) / proxy(中转) =====
        storage_upload_id = await self.storage.create_multipart(physical_key, mime_type)
        if self._supports_presign():
            try:
                part_count = -(-req.file_size_bytes // MULTIPART_PART_SIZE)
                part_urls = [
                    await self.storage.presign_put(
                        physical_key, storage_upload_id, n + 1, _PRESIGN_EXPIRES
                    )
                    for n in range(part_count)
                ]
                if all(part_urls):
                    token = self._make_multipart_token(
                        physical_key, storage_upload_id, req.content_hash, "direct"
                    )
                    logger.info(
                        f"直传初始化: {req.filename} ({req.file_size_bytes}B, "
                        f"{part_count}片) dir={dir_path or '/'}"
                    )
                    return MultipartInitResponse(
                        is_existing=False,
                        upload_id=token,
                        part_size=MULTIPART_PART_SIZE,
                        mode="direct",
                        part_urls=part_urls,
                    )
            except Exception as e:
                # 签名失败降级为中转,不阻断上传
                logger.warning(f"预签名生成失败,降级为中转模式: {e}")
        token = self._make_multipart_token(
            physical_key, storage_upload_id, req.content_hash, "proxy"
        )
        logger.info(
            f"中转初始化: {req.filename} ({req.file_size_bytes}B) dir={dir_path or '/'}"
        )
        return MultipartInitResponse(
            is_existing=False, upload_id=token, part_size=MULTIPART_PART_SIZE, mode="proxy"
        )

    async def upload_multipart_part(
        self, upload_id: str, part_number: int, content: bytes
    ) -> MultipartPartInfo:
        """
        上传单个分片(凭证即会话,免查库)
        :param upload_id: 分片会话凭证(init 返回)
        :param part_number: 分片号(从1开始)
        :param content: 分片二进制内容
        """
        if not 1 <= part_number <= 10000:
            raise ValueError("分片号必须在 1~10000 范围内")
        if len(content) > MULTIPART_PART_SIZE:
            raise ValueError(f"单片大小不能超过 {MULTIPART_PART_SIZE // 1024 // 1024}MB")
        data = self._parse_multipart_token(upload_id)
        result = await self.storage.upload_part(
            data["key"], data["uid"], part_number, content
        )
        return MultipartPartInfo(**result)

    async def list_multipart_parts(self, upload_id: str) -> list[MultipartPartInfo]:
        """
        查询会话中已上传的分片(断点续传)
        :param upload_id: 分片会话凭证
        """
        data = self._parse_multipart_token(upload_id)
        parts = await self.storage.list_parts(data["key"], data["uid"])
        return [MultipartPartInfo(**p) for p in parts]

    async def _reconcile_parts(
        self, data: dict, req_parts: list[MultipartPartInfo]
    ) -> list[dict]:
        """
        分片对账(直传完成前校验): 存储侧实际分片 vs 前端提交清单
        校验分片号连续、存储中真实存在、大小一致;ETag 双方都有时比对
        :param data: 会话凭证数据(key/uid)
        :param req_parts: 前端提交的分片列表
        :return: 对账通过的分片列表(补充存储侧ETag,供complete合并)
        """
        actual = await self.storage.list_parts(data["key"], data["uid"])
        actual_map = {p["part_number"]: p for p in actual}
        sorted_parts = sorted(req_parts, key=lambda p: p.part_number)
        for i, p in enumerate(sorted_parts):
            if p.part_number != i + 1:
                raise ValueError(f"分片不连续: 缺少第 {i + 1} 片")
            ap = actual_map.get(p.part_number)
            if not ap:
                raise ValueError(
                    f"分片 {p.part_number} 未在存储中找到,请重新上传该分片"
                )
            if p.size and p.size != ap["size"]:
                raise ValueError(
                    f"分片 {p.part_number} 大小不一致(声明{p.size}B/实际{ap['size']}B)"
                )
            if (
                p.etag
                and ap.get("etag")
                and p.etag.strip('"') != str(ap["etag"]).strip('"')
            ):
                raise ValueError(f"分片 {p.part_number} 校验值(ETag)不一致")
        # 以前端分片顺序为准,ETag 缺失时用存储侧记录补齐(S3 complete 必需)
        return [
            {
                "part_number": p.part_number,
                "etag": p.etag.strip('"')
                if p.etag
                else str(actual_map[p.part_number]["etag"]).strip('"'),
                "size": p.size or actual_map[p.part_number]["size"],
            }
            for p in sorted_parts
        ]

    @DaoRel
    async def complete_multipart_upload(
        self,
        upload_id: str,
        req: MultipartCompleteRequest,
        owner_user_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> FileEntry:
        """
        完成上传: 分片对账 -> 存储侧合并归位 -> 建条目(数据面不经过服务端)
        :param upload_id: 分片会话凭证
        :param req: 完成请求(文件名/分片清单)
        :param owner_user_id: 上传者ID
        :return: 新建的文件条目
        """
        data = self._parse_multipart_token(upload_id)
        dir_path = await self._validate_parent_dir(req.pid, session)
        if await self.file_entry_dao.exists_by_pid_name(
            req.pid, req.filename, session=session
        ):
            raise ValueError(f"当前目录下已存在同名文件: {req.filename}")

        if data.get("mode") == "direct":
            # 直传: 先与存储侧对账(防伪造清单),归位信任前端SHA-256(凭证签发阶段已校验)
            parts = await self._reconcile_parts(data, req.parts)
            real_hash, size, final_key = await self.storage.complete_multipart(
                data["key"], data["uid"], parts, expected_hash=data["hash"]
            )
        else:
            # 中转: 分片完整性预校验(连续性/单片大小),存储侧合并时算真实SHA-256
            parts = sorted(req.parts, key=lambda p: p.part_number)
            for i, p in enumerate(parts):
                if p.part_number != i + 1:
                    raise ValueError(f"分片不连续: 缺少第 {i + 1} 片")
                if i < len(parts) - 1 and p.size and p.size != MULTIPART_PART_SIZE:
                    raise ValueError(f"分片 {p.part_number} 大小不合法")
            real_hash, size, final_key = await self.storage.complete_multipart(
                data["key"], data["uid"], [p.model_dump() for p in parts]
            )

        if req.file_size_bytes and req.file_size_bytes != size:
            raise ValueError(
                f"合并后大小({size}B)与声明大小({req.file_size_bytes}B)不一致"
            )
        # 内容记录归位: 前端SHA-256与存储侧实际哈希不一致时(仅中转可能出现)校正记录
        claimed_hash = data["hash"]
        if claimed_hash != real_hash:
            dup = await self.file_content_dao.get_by_content_hash(real_hash, session)
            if dup:
                await self.file_content_dao.delete(claimed_hash, session)
            else:
                await self.file_content_dao.replace_content_hash(
                    claimed_hash, real_hash, final_key, session
                )
        else:
            await self.file_content_dao.update(
                claimed_hash,
                FileContentUpdate(physical_storage=final_key, file_size_bytes=size),
                session,
            )
        mime_type = self._guess_mime(req.filename) or "application/octet-stream"
        entry = await self._create_entry_from_content(
            req.filename, req.pid, dir_path, real_hash, size,
            mime_type, req.description, owner_user_id, session,
        )
        logger.info(f"上传完成({data.get('mode')}): {req.filename} -> {entry.logical_path} ({size}B)")
        return entry

    async def abort_multipart_upload(self, upload_id: str) -> None:
        """
        取消分片上传会话(清理存储侧已上传分片,内容记录保留待后续复用)
        :param upload_id: 分片会话凭证
        """
        data = self._parse_multipart_token(upload_id)
        await self.storage.abort_multipart(data["key"], data["uid"])
        logger.info(f"分片上传已取消: {data['key']}")

    @DaoRel
    async def create_entry(
        self,
        req: EntryCreateRequest,
        owner_user_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> FileEntry:
        """
        基于已完成的内容记录创建文件条目(秒传场景: init 返回 is_existing 后调用)
        :param req: 条目创建请求(文件名/内容哈希)
        :param owner_user_id: 上传者ID
        :return: 新建的文件条目
        """
        content = await self.file_content_dao.get_by_content_hash(
            req.content_hash, session
        )
        if not content or content.content_status != TaskStatus.SUCCESS:
            raise ValueError("文件内容不存在或未完成上传,无法创建条目")
        dir_path = await self._validate_parent_dir(req.pid, session)
        if await self.file_entry_dao.exists_by_pid_name(
            req.pid, req.name, session=session
        ):
            raise ValueError(f"当前目录下已存在同名文件: {req.name}")
        return await self._create_entry_from_content(
            req.name, req.pid, dir_path, req.content_hash, req.file_size_bytes,
            req.mime_type, req.description, owner_user_id, session,
        )

    def get_upload_mode(self) -> UploadModeResponse:
        """
        查询上传模式(前端上传前获取一次,决定直传/中转策略)
        - direct: S3协议存储,前端预签名直传,数据面不经过服务端
        - proxy: 本地磁盘存储,数据面经服务端中转
        """
        return UploadModeResponse(
            mode="direct" if self._supports_presign() else "proxy",
            part_size=MULTIPART_PART_SIZE,
            max_size=storage_config.max_size,
        )

    async def presign_download_url(
        self, file_key: str, filename: str, expires: int = _PRESIGN_EXPIRES
    ) -> str | None:
        """
        生成下载直链(直传存储返回预签名URL;local 不支持返回None走流式代理)
        :param file_key: 物理存储键
        :param filename: 下载时的文件名(Content-Disposition)
        """
        if not self._supports_presign():
            return None
        try:
            return await self.storage.presign_get(file_key, expires, filename)
        except Exception as e:
            logger.warning(f"下载直链生成失败,降级为流式代理: {e}")
            return None

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
        用途: 配置切换 local<->s3 前,先迁移历史数据实现无缝切换
        :param req: MigrateRequest(from_type/to_type)
        :return: 迁移结果 {total, migrated, skipped, failed}
        """
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
