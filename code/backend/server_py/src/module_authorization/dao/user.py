from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func, update
from common.utils.db.schema.pagination import (
    PaginationParams,
)
from common.config.db import DaoRel
from module_authorization.do.user import User, UserCreate, UserUpdate
from module_authorization.do.user import UserResponse


class UserDao:
    @DaoRel
    async def add(
        self, user: UserCreate, session: AsyncSession | None = None
    )->UserResponse:
        """
        新增用户记录
        :param user: 用户创建数据
        :param session: 可选数据库会话
        :return: 新创建用户信息
        """
        db_user = User.model_validate(user.model_dump(exclude_unset=True))
        session.add(db_user)
        await session.flush()
        # 去除密码字段 转换为响应模型
        user_data = db_user.model_dump(exclude={"password"})
        return UserResponse.model_validate(user_data)
    
    @DaoRel
    async def delete(self, id, session: AsyncSession | None = None):
        """
        删除用户记录
        :param id: 要删除的用户ID
        :param session: 可选数据库会话
        """
        user = await session.get(User, id)
        if not user:
            raise ValueError(f"未找到ID为 {id} 的用户")
        await session.delete(user)
        await session.flush()

    @DaoRel
    async def update(
        self,
        user_id: str,
        user: UserUpdate,
        session: AsyncSession | None = None,
    ):
        """
        直接更新用户记录（不先查询）
        :param user_id: 要更新的用户ID
        :param user: 用户更新数据
        :param session: 可选数据库会话
        :return: 更新成功的用户ID
        :raises: ValueError 如果用户不存在
        """
        # 准备更新数据（排除未设置的字段）
        update_data = user.model_dump(exclude_unset=True)

        # 执行直接更新
        stmt = update(User).where(User.id == user_id).values(**update_data)

        result = await session.exec(stmt)

        # 检查是否实际更新了记录
        if result.rowcount == 0:
            raise ValueError(f"未找到ID为 {user_id} 的用户")
        await session.flush()

    @DaoRel
    async def get(self, id, session: AsyncSession | None = None):
        """
        查询单个用户
        :param id: 要查询的用户ID
        :param session: 可选数据库会话
        :return: 用户对象，未找到返回None
        """
        user = await session.get(User, id)
        if not user:
            raise ValueError(f"未找到ID为 {id} 的用户")
        user_data = user.model_dump(exclude={"password"})
        return UserResponse.model_validate(user_data)

    @DaoRel
    async def get_by_username(self, username, session: AsyncSession | None = None):
        """
        根据用户名查询用户
        :param username: 用户名
        :param session: 可选数据库会话
        :return: 用户对象，未找到返回None
        """
        stmt = select(User).where(User.username == username)
        result = await session.exec(stmt)
        return result.first()

    @DaoRel
    async def list(
        self, pagination: PaginationParams, session: AsyncSession | None = None
    ):
        """
        分页查询用户列表
        :param pagination: 分页参数
        :param session: 可选数据库会话
        :return: 用户列表
        """
        statement = select(User).offset(pagination.offset).limit(pagination.limit)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def count(self, session: AsyncSession | None = None):
        """
        获取用户总数
        :param session: 可选数据库会话
        :return: 用户总数
        """
        statement = select(func.count()).select_from(User)
        result = await session.exec(statement)
        return result.one()