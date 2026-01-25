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
    PresignedUrlRequest,
)
from module_file.dao.filesystem import FileDao
from module_file.config.filesystem import storage
import hashlib
import secrets  # 导入secrets模块
from uuid import uuid4  # 导入uuid4
from fastapi import UploadFile, HTTPException
import aiofiles
from pathlib import Path
from common.config.path import DIR_UPLOAD
import logging
import io

# 配置日志
logger = logging.getLogger(__name__)


class FileService:
    """文件服务类，提供文件上传、下载、管理等功能"""

    def __init__(self, file_dao: FileDao | None = None, storage_interface=None):
        """
        初始化文件服务
        :param file_dao: 文件数据访问对象，可选
        :param storage_interface: 存储接口实现，可选
        """
        self.file_dao = file_dao or FileDao()
        self.storage = storage_interface or storage

    async def add(self, file: FileEntryCreate) -> str:
        """
        添加文件记录
        :param file: 文件创建数据
        :return: 新创建文件的ID
        """
        return await self.file_dao.add(file)

    async def delete(self, id: str):
        """
        删除文件记录和物理文件
        :param id: 文件ID
        """
        try:
            # 先获取文件信息
            file_info = await self.get(id)
            if file_info:
                # 尝试删除物理文件
                try:
                    file_path = Path(file_info.physical_storage)
                    if file_path.exists():
                        file_path.unlink()
                        logger.info(f"已删除物理文件: {file_path}")
                except Exception as e:
                    logger.error(f"删除物理文件失败: {e}")

                # 删除数据库记录
                await self.file_dao.delete(id)
                logger.info(f"已删除文件记录: {id}")
            else:
                logger.warning(f"尝试删除不存在的文件: {id}")
        except Exception as e:
            logger.error(f"删除文件时发生错误: {e}")
            raise

    async def update(self, file_id: str, file_update: FileEntryUpdate):
        """
        更新文件信息并返回更新后的文件信息（在同一事务中）
        :param file_id: 文件ID
        :param file_update: 更新数据
        :return: 更新后的文件信息
        :raises: ValueError 如果文件不存在
        """
        return await self.file_dao.update(file_id, file_update)

    async def get(self, id: str) -> FileEntry | None:
        """
        获取文件信息
        :param id: 文件ID
        :return: 文件信息对象，不存在返回None
        """
        return await self.file_dao.get(id)

    async def list_all(self, pagination: PaginationParams) -> PaginationResponse:
        """
        分页查询所有文件
        :param pagination: 分页参数
        :return: 分页响应结果
        """
        items = await self.file_dao.list_all(pagination)
        total = await self.file_dao.count()
        return PaginationResponse.create(items, total, pagination)

    async def get_scroll(self, params: InfiniteScrollParams) -> InfiniteScrollResponse:
        """
        滚动加载文件列表
        :param params: 滚动参数
        :return: 滚动响应结果
        """
        items: list = await self.file_dao.get_scroll(params)
        return InfiniteScrollResponse.create(items, params.limit)

    async def calculate_md5(self, file_path: str) -> str:
        """
        计算文件的MD5值
        :param file_path: 文件路径
        :return: MD5哈希值
        """
        md5_hash = hashlib.md5()
        async with aiofiles.open(file_path, "rb") as f:
            while chunk := await f.read(8192):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()

    async def upload_file(
        self, file: UploadFile, description: str = None, owner_user_id: str = None
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

            # 计算MD5值 最好单独有个接口前端校验md5是否一致
            content_hash = hashlib.md5(content).hexdigest()

            # 检查文件是否已存在(通过MD5)
            existing_file = await self.file_dao.get_by_content_hash(content_hash)

            if existing_file:
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

            created_file_id = await self.file_dao.add(file_create)
            logger.info(
                f"文件上传成功: {file_create.name} -> {file_create.logical_path}"
            )
            return await self.file_dao.get(created_file_id)
        except Exception as e:
            logger.error(f"上传文件时发生错误: {e}")
            raise

    async def generate_presigned_url(
        self, presigned_url_request: PresignedUrlRequest
    ) -> str | None:
        """
        生成预签名URL
        :param presigned_url_request: 预签名URL请求模型
        :return: 预签名URL
        """
        try:
            presigned_url = await self.storage.generate_presigned_url(
                presigned_url_request.filename,
                presigned_url_request.content_type,
            )
            return presigned_url
        except Exception as e:
            logger.error(f"生成预签名URL时发生错误: {e}")
            raise

    async def upload_with_presigned_url(self, presigned_url: str, data: bytes) -> bool:
        """
        使用预签名URL上传数据
        :param presigned_url: 预签名URL
        :param data: 要上传的数据
        :return: 是否上传成功
        """
        try:
            success = await self.storage.upload_with_presigned_url(presigned_url, data)
            return success
        except Exception as e:
            logger.error(f"使用预签名URL上传时发生错误: {e}")
            raise

    async def download_with_presigned_url(self, presigned_url: str) -> bytes | None:
        """
        使用预签名URL下载数据
        :param presigned_url: 预签名URL
        :return: 文件数据或None
        """
        try:
            data = await self.storage.download_with_presigned_url(presigned_url)
            return data
        except Exception as e:
            logger.error(f"使用预签名URL下载时发生错误: {e}")
            raise

    async def delete_with_presigned_url(self, presigned_url: str) -> bool:
        """
        使用预签名URL删除数据
        :param presigned_url: 预签名URL
        :return: 是否删除成功
        """
        try:
            success = await self.storage.delete_with_presigned_url(presigned_url)
            return success
        except Exception as e:
            logger.error(f"使用预签名URL删除时发生错误: {e}")
            raise

    async def get_file_info_for_download(self, file_id: str) -> tuple[str, str, str]:
        """
        获取文件下载所需的信息
        :param file_id: 文件ID
        :return: (文件名, MIME类型, 物理存储路径)
        """
        try:
            file_info = await self.file_dao.get(file_id)
            if not file_info or not file_info.is_active:
                logger.warning(f"文件不存在或已被禁用: {file_id}")
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
