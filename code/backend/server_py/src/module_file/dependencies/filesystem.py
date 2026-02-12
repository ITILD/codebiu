from fastapi import Depends

from module_file.dao.file_entry_dao import FileEntryDao
from module_file.dao.file_content_dao import FileContentDao
from module_file.service.filesystem import FileService


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
    """Service工厂"""
    return FileService(file_entry_dao, file_content_dao)
