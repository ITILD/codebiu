from fastapi import Depends

from module_file.dao.filesystem import FileDao
from module_file.service.filesystem import FileService

async def get_file_dao() -> FileDao:
    """DAO工厂"""
    return FileDao()

# 新增的依赖项工厂函数
async def get_file_service(dao: FileDao = Depends(get_file_dao)) -> FileService:
    """Service工厂"""
    return FileService(dao)