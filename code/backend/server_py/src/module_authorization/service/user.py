from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_authorization.do.user import User, UserCreate, UserUpdate, UserResponse
from module_authorization.dao.user import UserDao
from common.utils.security.password import verify_password,hash_password

class UserService:
    """用户服务"""

    def __init__(self, user_dao: UserDao):
        """依赖注入构造器:初始化所需的数据访问对象"""
        self.user_dao = user_dao or UserDao()

    async def add(self, user: UserCreate)->UserResponse:
        """
        创建用户(分配内置角色;首个用户自动引导为全局管理员)
        :param user: 用户创建数据
        :return: 创建的用户ID
        """
        # 检查用户名是否已存在
        existing_user = await self.user_dao.get_by_username(user.username)
        if existing_user:
            raise ValueError(f"用户名 '{user.username}' 已存在")
        # 首个注册用户自动引导为全局管理员(bootstrap)
        is_first_user = await self.user_dao.count() == 0
        # 密码进行加密处理
        user.password = hash_password(user.password)
        user = await self.user_dao.add(user)

        # 分配内置角色(admin/user,幂等,失败不影响用户创建)
        try:
            from module_authorization.dependencies.permission import (
                sync_default_user_roles,
            )
            await sync_default_user_roles(user.id, is_first_user)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"分配默认角色失败: {e}")
        return user

    async def delete(self, user_id: str):
        """
        删除用户
        :param user_id: 用户ID
        """
        await self.user_dao.delete(user_id)

    async def update(self, user_id: str, user: UserUpdate):
        """
        更新用户
        :param user_id: 用户ID
        :param user: 用户更新数据
        """
        # 加密处理
        if user.password:
            user.password = hash_password(user.password)
        await self.user_dao.update(user_id, user)

    async def get(self, user_id: str) -> User | None:
        """
        获取用户详情
        :param user_id: 用户ID
        :return: 用户对象
        """
        return await self.user_dao.get(user_id)

    async def get_by_username(self, username: str) -> User | None:
        """
        根据用户名获取用户
        :param username: 用户名
        :return: 用户对象
        """
        return await self.user_dao.get_by_username(username)

    async def list_paged(
        self,
        pagination: PaginationParams,
        username: str | None = None,
        nickname: str | None = None,
        is_active: bool | None = None,
    ) -> PaginationResponse:
        """
        分页获取用户列表(支持多字段过滤)
        :param pagination: 分页参数
        :param username: 用户名模糊匹配
        :param nickname: 昵称模糊匹配
        :param is_active: 状态精确过滤(启用/禁用)
        :return: 分页用户列表
        """
        items = await self.user_dao.list_paged(
            pagination, username=username, nickname=nickname, is_active=is_active
        )
        total = await self.user_dao.count(
            username=username, nickname=nickname, is_active=is_active
        )
        return PaginationResponse.create(items, total, pagination)

    async def authenticate(self, username: str, password: str) -> User | None:
        """
        用户认证
        :param username: 用户名
        :param password: 密码
        :return: 认证成功的用户对象，失败返回None
        """
        # 密码哈希验证
        user = await self.get_by_username(username)
        if user and verify_password(password, user.password):
            return user
        return None