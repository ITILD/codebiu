# self
from common.utils.db.schema.pagination import InfiniteScrollParams, InfiniteScrollResponse, PaginationParams, PaginationResponse
from module_file.do.file import File, FileCreate, FileUpdate
from module_file.dao.file import FileDao
import hashlib
import secrets  # 导入secrets模块
from fastapi import UploadFile, HTTPException
import aiofiles
from pathlib import Path
from common.config.path import DIR_UPLOAD

class FileService:
    """file"""

    def __init__(self, file_dao: FileDao):
        self.file_dao = file_dao or FileDao()
        self.upload_dir = Path(DIR_UPLOAD)

    async def add(self, file: FileCreate) -> str:
        return await self.file_dao.add(file)

    async def delete(self, id: str):
        # 先获取文件信息
        file_info = await self.get(id)
        if file_info:
            # 尝试删除物理文件
            try:
                file_path = Path(file_info.file_path)
                if file_path.exists():
                    file_path.unlink()
            except Exception as e:
                print(f"删除物理文件失败: {e}")
            # 删除数据库记录
            await self.file_dao.delete(id)

    async def update(self, file_id: str, file: FileUpdate):
        await self.file_dao.update(file_id, file)

    async def get(self, id: str) -> File | None:
        return await self.file_dao.get(id)
    
    async def list_all(self, pagination: PaginationParams):
        items = await self.file_dao.list_all(pagination)
        total = await self.file_dao.count()
        return PaginationResponse.create(items, total, pagination)
    
    async def get_scroll(self, params: InfiniteScrollParams):
        items:list = await self.file_dao.get_scroll(params)
        return InfiniteScrollResponse.create(items, params.limit)

    async def calculate_md5(self, file_path: str) -> str:
        """
        计算文件的MD5值
        :param file_path: 文件路径
        :return: MD5哈希值
        """
        md5_hash = hashlib.md5()
        async with aiofiles.open(file_path, 'rb') as f:
            while chunk := await f.read(8192):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()

    async def upload_file(
        self, 
        file: UploadFile,
        description: str = None,
        uploaded_by: str = None
    ) -> File:
        """
        上传文件
        :param file: 上传的文件对象
        :param description: 文件描述
        :param uploaded_by: 上传者ID
        :return: 文件信息对象
        """
        # 生成唯一文件名
        file_ext = Path(file.filename).suffix
        # 使用secrets.token_bytes替代os.urandom，提供更好的密码学安全性
        unique_filename = f"{hashlib.md5(secrets.token_bytes(16)).hexdigest()}{file_ext}"
        file_path = self.upload_dir / unique_filename
        # 保存文件
        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await file.read()
            await out_file.write(content)

        # 计算MD5值
        md5 = hashlib.md5(content).hexdigest()

        # 检查文件是否已存在（通过MD5）
        existing_file = await self.file_dao.get_by_md5(md5)
        if existing_file:
            # 如果文件已存在，删除刚刚上传的文件返回存在的
            file_path.unlink()
            return existing_file

        # 创建文件记录
        file_create = FileCreate(
            file_name=file.filename,
            file_path=str(file_path),
            file_size=len(content),
            file_type=file_ext[1:] if file_ext else '',  # 去掉点号
            mime_type=file.content_type or 'application/octet-stream',
            md5=md5,
            description=description,
            uploaded_by=uploaded_by,
            is_active=True
        )

        file_id = await self.file_dao.add(file_create)
        return await self.file_dao.get(file_id)

    async def download_file(self, file_id: str) -> tuple[str, str, bytes]:
        """
        下载文件
        :param file_id: 文件ID
        :return: (文件名, MIME类型, 文件内容)
        """
        file_info = await self.file_dao.get(file_id)
        if not file_info or not file_info.is_active:
            raise HTTPException(status_code=404, detail="文件不存在或已被禁用")

        file_path = Path(file_info.file_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="文件已丢失")

        # 读取文件内容
        async with aiofiles.open(file_path, 'rb') as f:
            content = await f.read()

        return file_info.file_name, file_info.mime_type, content