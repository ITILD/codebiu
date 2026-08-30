from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, update
from common.config.db import DaoRel
from module_rag.do.user_model import UserModel, UserModelUpdate


class UserModelDao:
    """用户-模型绑定数据访问对象"""

    @DaoRel
    async def add(
        self, user_model: UserModel, session: AsyncSession | None = None
    ) -> str:
        """
        新增用户-模型绑定记录
        :param user_model: 用户-模型绑定数据
        :param session: 可选数据库会话
        :return: 新创建记录的ID
        """
        session.add(user_model)
        await session.flush()
        return user_model.id

    @DaoRel
    async def get_by_user(
        self, user_id: str, session: AsyncSession | None = None
    ) -> UserModel | None:
        """
        根据用户ID查询模型绑定
        :param user_id: 用户ID
        :param session: 可选数据库会话
        :return: 用户-模型绑定对象，未找到返回None
        """
        statement = select(UserModel).where(UserModel.user_id == user_id)
        result = await session.exec(statement)
        return result.first()

    @DaoRel
    async def update_by_user(
        self,
        user_id: str,
        user_model: UserModelUpdate,
        session: AsyncSession | None = None,
    ):
        """
        更新用户-模型绑定记录
        :param user_id: 用户ID
        :param user_model: 更新数据
        :param session: 可选数据库会话
        """
        update_data = user_model.model_dump(exclude_unset=True)
        stmt = (
            update(UserModel)
            .where(UserModel.user_id == user_id)
            .values(**update_data)
        )
        result = await session.exec(stmt)
        if result.rowcount == 0:
            raise ValueError(f"未找到用户 {user_id} 的模型绑定记录")
        await session.flush()
