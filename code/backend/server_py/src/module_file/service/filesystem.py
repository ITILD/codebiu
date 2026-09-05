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
from uuid import uuid4  # 导入uuid4
from fastapi import UploadFile, HTTPException
import aiofiles
from sqlmodel.ext.asyncio.session import AsyncSession
from common.config.db import DaoRel
from pathlib import Path, PosixPath
from module_file.do.filesystem import FileContent, FileContentCreate
import logging
from module_file.utils.multi_storage.do.storage_config import PresignedType
from common.config.index import conf
from datetime import datetime
from common.enum.task import TaskStatus

# from module_file.config.filetype import mimetypes
# 配置日志
logger = logging.getLogger(__name__)


class FileService:
    """文件服务类，提供文件上传、下载、管理等功能"""

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

    async def add(self, file: FileEntryCreate) -> str:
        """
        添加文件或目录记录
        :param file: 文件创建数据
        :return: 新创建文件或目录的ID
        """
        return await self.file_entry_dao.add(file)

    @DaoRel
    async def delete_file(self, id: str, session: AsyncSession | None = None):
        """
        删除文件记录
        :param id: 文件ID
        """
        try:
            # 先获取文件信息
            file_info = await self.file_entry_dao.get(id, session)
            if not file_info:
                raise ValueError(f"未找到ID为 {id} 的文件")
            # 逻辑删除
            await self.file_entry_dao.soft_delete(id, session)
            # 更改引用计数 -1
            await self.file_content_dao.ref_count_change(
                file_info.content_hash, -1, session
            )
        except Exception as e:
            logger.error(f"删除文件时发生错误: {e}")
            raise

    @DaoRel
    async def delete_folder(
        self, folder_id: str, session: AsyncSession | None = None, is_fast: bool = False
    ):
        """
        删除目录记录
        :param folder_id: 目录ID
        """
        try:
            # 先直接删除当前目录
            await self.file_entry_dao.soft_delete(folder_id, session)
            # 递归更新并批量删除子目录和子文件   is_fast模式  安全性低 asyncio.create_task  递归 CTE??

            # # 先获取目录信息
            # file_entry_ids = await self.file_entry_dao.get_subtree_ids(id, session)
            # if not file_entry_ids:
            #     raise ValueError(f"未找到ID为 {id} 的目录")
            # # 递归更新并批量删除子目录和子文件

            # # 逻辑删除
            # await self.file_entry_dao.soft_delete(id, session)
            # # 更改引用计数 -1
            # await self.file_content_dao.ref_count_change(
            #     file_info.content_hash, -1, session
            # )
        except Exception as e:
            logger.error(f"删除目录时发生错误: {e}")
            raise

    async def update(self, file_id: str, file_update: FileEntryUpdate):
        """
        更新文件信息并返回更新后的文件信息（在同一事务中）
        :param file_id: 文件ID
        :param file_update: 更新数据
        :return: 更新后的文件信息
        :raises: ValueError 如果文件不存在
        """
        return await self.file_entry_dao.update(file_id, file_update)

    async def get_file_entry(self, id: str) -> FileEntry | None:
        """
        获取文件或目录信息
        :param id: 文件或目录的ID
        :return: 文件或目录信息对象，不存在返回None
        """
        return await self.file_entry_dao.get(id)

    async def list_all(self, pagination: PaginationParams) -> PaginationResponse:
        """
        分页查询所有文件
        :param pagination: 分页参数
        :return: 分页响应结果
        """
        items = await self.file_entry_dao.list_all(pagination)
        total = await self.file_entry_dao.count()
        return PaginationResponse.create(items, total, pagination)

    async def get_scroll(self, params: InfiniteScrollParams) -> InfiniteScrollResponse:
        """
        滚动加载文件列表
        :param params: 滚动参数
        :return: 滚动响应结果
        """
        items: list = await self.file_entry_dao.get_scroll(params)
        return InfiniteScrollResponse.create(items, params.limit)

    # async def calculate_md5(self, file_path: str) -> str:
    #     """
    #     计算文件的MD5值
    #     :param file_path: 文件路径
    #     :return: MD5哈希值
    #     """
    #     md5_hash = hashlib.md5()
    #     async with aiofiles.open(file_path, "rb") as f:
    #         while chunk := await f.read(8192):
    #             md5_hash.update(chunk)
    #     return md5_hash.hexdigest()

    ####################################纯本地存储##############################################
    async def upload_file(
        self,
        file: UploadFile,
        description: str = None,
        existing_id: str = None,
        content_hash: str = None,
        owner_user_id: str = None,
    ) -> FileEntry:
        """
        上传文件
        :param file: 上传的文件对象
        :param description: 文件描述
        :param owner_user_id: 上传者ID
        :return: 文件信息对象
        """
        try:
            # 先读取文件内容到内存
            content = await file.read()

            # # 计算MD5值 最好单独有个接口前端校验md5是否一致 content_hash应该前端获取
            # content_hash = hashlib.md5(content).hexdigest()

            # # 检查文件是否已存在(通过MD5)
            # existing_file = await self.file_entry_dao.get_by_content_hash(content_hash)
            # 获取已存在信息
            existing_file = await self.file_entry_dao.get(existing_id)

            if existing_id:
                # 文件已存在，复用现有文件信息
                file_create = FileEntryCreate(
                    name=existing_file.name,
                    logical_path=existing_file.logical_path,
                    physical_storage=existing_file.physical_storage,
                    file_size_bytes=existing_file.file_size_bytes,
                    file_extension=existing_file.file_extension,
                    mime_type=existing_file.mime_type,
                    content_hash=existing_file.content_hash,
                    description=existing_file.description,
                    owner_user_id=owner_user_id,
                    is_active=True,
                )
            else:
                # 文件不存在，生成新文件名并保存
                file_ext = Path(file.filename).suffix
                unique_filename = f"{uuid4().hex}{file_ext}"

                # 使用存储接口保存文件
                file_key = f"uploads/{unique_filename}"
                await self.storage.save(file_key, content)

                # 创建新文件记录
                file_create = FileEntryCreate(
                    name=file.filename,
                    logical_path=f"/{file_key}",
                    physical_storage=file_key,  # 存储键而不是本地路径
                    file_size_bytes=len(content),
                    file_extension=file_ext[1:] if file_ext else "",
                    mime_type=file.content_type or "application/octet-stream",
                    content_hash=content_hash,
                    description=description,
                    owner_user_id=owner_user_id,
                    is_active=True,
                )

            created_file_id = await self.file_entry_dao.add(file_create)
            logger.info(
                f"文件上传成功: {file_create.name} -> {file_create.logical_path}"
            )
            return await self.file_entry_dao.get(created_file_id)
        except Exception as e:
            logger.error(f"上传文件时发生错误: {e}")
            raise

    async def get_file_info_for_download(
        self, file_content_id: str
    ) -> tuple[str, str, str]:
        """
        获取文件下载所需的信息
        :param file_content_id: 文件ID
        :return: (文件名, MIME类型, 物理存储路径)
        """
        try:
            file_info = await self.file_entry_dao.get(file_content_id)
            if not file_info or not file_info.is_active:
                logger.warning(f"文件不存在或已被禁用: {file_content_id}")
                raise HTTPException(status_code=404, detail="文件不存在或已被禁用")

            # 使用存储接口检查文件是否存在
            file_exists = await self.storage.exists(file_info.physical_storage)
            if not file_exists:
                logger.error(f"物理文件不存在: {file_info.physical_storage}")
                raise HTTPException(status_code=404, detail="物理文件不存在")

            return file_info.name, file_info.mime_type, file_info.physical_storage
        except Exception as e:
            logger.error(f"获取文件信息时发生错误: {e}")
            raise f"获取文件信息时发生错误: {e}"

    async def stream_file_content(self, file_path: str, chunk_size: int = 8192):
        """
        流式读取文件内容
        :param file_path: 文件路径
        :param chunk_size: 每次读取的块大小
        :yield: 文件内容块
        """
        try:
            # 使用存储接口加载文件内容
            content = await self.storage.load(file_path)
            # 将内容分块发送
            for i in range(0, len(content), chunk_size):
                yield content[i : i + chunk_size]
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
