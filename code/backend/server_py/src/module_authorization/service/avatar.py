import logging
import re
from pathlib import Path

from fastapi import UploadFile

from module_authorization.dao.user import UserDao
from module_authorization.do.user import UserUpdate
from module_file.service.filesystem import FileService

logger = logging.getLogger(__name__)

# 头像模块在虚拟目录树中的模块根(source_module 标记; 该标记条目允许匿名下载)
AVATAR_MODULE_KEY = "avatar"
AVATAR_MODULE_LABEL = "用户头像"

# 允许上传的图片扩展名(不含点)
ALLOWED_IMAGE_EXTS = {"png", "jpg", "jpeg", "gif", "webp", "svg", "bmp"}


class AvatarService:
    """用户头像服务

    注入统一文件服务(FileService), 头像等用户相关文件统一存于虚拟目录
    /用户头像/<用户ID>/ 下(source_module='avatar', 文件管理可见但只读,
    下载走 /file/filesystem/download/{entry_id} 且允许匿名访问)。
    """

    def __init__(
        self,
        file_service: FileService | None = None,
        user_dao: UserDao | None = None,
    ):
        """依赖注入构造器: 统一文件服务 + 用户DAO"""
        self.file_service = file_service or FileService()
        self.user_dao = user_dao or UserDao()

    @staticmethod
    def _extract_entry_id(avatar: str | None) -> str | None:
        """从历史头像字段解析文件条目ID(仅识别本服务写入的下载路径/裸条目ID格式)"""
        if not avatar:
            return None
        matched = re.search(r"/file/filesystem/download/([0-9a-f]{32})$", avatar)
        if matched:
            return matched.group(1)
        if re.fullmatch(r"[0-9a-f]{32}", avatar):
            return avatar
        return None

    async def upload_avatar(self, user_id: str, file: UploadFile) -> dict:
        """
        上传用户头像: 经统一文件服务存入 /用户头像/<用户ID>/ 并回写用户头像字段
        :param user_id: 当前登录用户ID
        :param file: 图片文件
        :return: {"avatar": 下载路径, "entry_id": 文件条目ID}
        :raises ValueError: 格式不允许
        """
        filename = file.filename or "avatar.png"
        ext = Path(filename).suffix.lstrip(".").lower()
        if ext not in ALLOWED_IMAGE_EXTS:
            raise ValueError(
                f"不支持的图片格式 '{ext}', 允许: {'/'.join(sorted(ALLOWED_IMAGE_EXTS))}"
            )

        # 幂等确保头像模块根目录与用户专属子目录
        root = await self.file_service.ensure_module_root(
            AVATAR_MODULE_KEY, AVATAR_MODULE_LABEL, user_id
        )
        folder = await self.file_service.ensure_folder(user_id, root.id, user_id)

        # 上传新头像(内容哈希去重, 内容引用计数由文件条目维护)
        entry = await self.file_service.upload_file(
            file, "用户头像", folder.id, owner_user_id=user_id
        )

        # 删除旧头像条目(仅当其属于 avatar 模块, 防止误删外部链接指向的条目)
        user = await self.user_dao.get(user_id)
        old_entry_id = self._extract_entry_id(user.avatar if user else None)
        if old_entry_id and old_entry_id != entry.id:
            try:
                old_entry = await self.file_service.get_file_entry(old_entry_id)
                if old_entry and old_entry.source_module == AVATAR_MODULE_KEY:
                    await self.file_service.delete_file(old_entry_id)
            except Exception as e:
                logger.warning(f"清理旧头像条目失败 {old_entry_id}: {e}")

        # 头像字段存 API 下载路径(匿名可访问, 前端 <img> 直接可用)
        avatar_url = f"/base_server/file/filesystem/download/{entry.id}"
        await self.user_dao.update(user_id, UserUpdate(avatar=avatar_url))
        return {"avatar": avatar_url, "entry_id": entry.id}

    async def delete_avatar(self, user_id: str) -> None:
        """
        删除当前头像还原默认(用户名首字头像): 清理 avatar 模块条目并置空用户头像字段
        :param user_id: 当前登录用户ID
        :raises ValueError: 当前无上传头像(字段为空)
        """
        user = await self.user_dao.get(user_id)
        if not user or not user.avatar:
            raise ValueError("当前未设置头像")
        # 清理 avatar 模块的头像文件条目(仅识别本服务写入的格式, 外部链接不动)
        entry_id = self._extract_entry_id(user.avatar)
        if entry_id:
            entry = await self.file_service.get_file_entry(entry_id)
            if entry and entry.source_module == AVATAR_MODULE_KEY:
                try:
                    await self.file_service.delete_file(entry_id)
                except Exception as e:
                    logger.warning(f"清理头像条目失败 {entry_id}: {e}")
        # 置空头像字段, 前端回退为用户名首字默认头像
        await self.user_dao.update(user_id, UserUpdate(avatar=None))
