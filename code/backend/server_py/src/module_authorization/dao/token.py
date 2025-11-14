from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, update, delete
from common.config.db import DaoRel
from module_authorization.do.token import Token, TokenCreate


class TokenDao:
    @DaoRel
    async def save_token(
        self, token_info:TokenCreate, session: AsyncSession | None = None
    ):
        """
        保存令牌信息到数据库
        :param token_info: 令牌信息字典
        :param session: 可选数据库会话
        :return: 保存的令牌对象
        """
        db_token = Token.model_validate(token_info)
        session.add(db_token)
        await session.flush()
        return db_token

    @DaoRel
    async def get_token_by_user_id(
        self, user_id, session: AsyncSession | None = None
    ):
        """
        根据用户ID获取令牌信息
        :param user_id: 用户ID  
        :param session: 可选数据库会话
        :return: 令牌对象，未找到返回None
        """
        stmt = select(Token).where(Token.user_id == user_id)
        result = await session.exec(stmt)
        return result.first()

    @DaoRel
    async def revoke_token_by_token_id(
        self, token_id, session: AsyncSession | None = None
    ):
        """
        撤销令牌
        :param session: 可选数据库会话
        :return: 撤销是否成功
        """
        stmt = update(Token).where(Token.id == token_id).values(is_revoked=True)
        result = await session.exec(stmt)
        await session.flush()
        return result.rowcount > 0

    @DaoRel
    async def delete_token(
        self, token, session: AsyncSession | None = None
    ):
        """
        删除令牌信息
        :param token: 访问令牌
        :param session: 可选数据库会话
        :return: 删除是否成功
        """
        stmt = delete(Token).where(Token.token == token)
        result = await session.exec(stmt)
        await session.flush()
        return result.rowcount > 0

    @DaoRel
    async def delete_tokens_by_user_id(
        self, user_id, session: AsyncSession | None = None
    ):
        """
        删除用户的所有令牌
        :param user_id: 用户ID
        :param session: 可选数据库会话
        :return: 删除是否成功
        """
        stmt = delete(Token).where(Token.user_id == user_id)
        result = await session.exec(stmt)
        await session.flush()
        return result.rowcount > 0