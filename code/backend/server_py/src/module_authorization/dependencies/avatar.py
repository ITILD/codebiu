from fastapi import Depends

from module_authorization.service.avatar import AvatarService
from module_file.dependencies.filesystem import get_file_service


async def get_avatar_service(
    file_service=Depends(get_file_service),
) -> AvatarService:
    """头像Service工厂(注入统一文件服务, 头像文件存于虚拟目录 /用户头像/ 下)"""
    return AvatarService(file_service)
