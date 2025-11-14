from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_authorization.do.user import User, UserCreate, UserUpdate, UserResponse
from module_authorization.dao.user import UserDao
from common.utils.security.password import verify_password,hash_password

class UserService:
    """用户服务"""

    def __init__(self, user_dao: UserDao):
        self.user_dao = user_dao

    async def add(self, user: UserCreate)->UserResponse:
        """
        创建用户
        :param user: 用户创建数据
        :return: 创建的用户ID
        """
        # 检查用户名是否已存在
        existing_user = await self.user_dao.get_by_username(user.username)
        if existing_user:
            raise ValueError(f"用户名 '{user.username}' 已存在")
        # 密码进行加密处理
        user.password = hash_password(user.password)
        return await self.user_dao.add(user)

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

    async def list(self, pagination: PaginationParams) -> PaginationResponse:
        """
        分页获取用户列表
        :param pagination: 分页参数
        :return: 分页用户列表
        """
        items = await self.user_dao.list(pagination)
        total = await self.user_dao.count()
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