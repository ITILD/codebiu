from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func, update
from common.config.db import DaoRel
from module_rag.do.conversation import Conversation, ConversationCreate, ConversationUpdate


class ConversationDao:
    """对话数据访问对象"""

    @DaoRel
    async def add(
        self, conversation: Conversation, session: AsyncSession | None = None
    ) -> str:
        """新增对话记录

        :param conversation: 对话对象
        :param session: 可选数据库会话(事务内复用)
        :return: 新建对话的ID
        """
        session.add(conversation)
        await session.flush()
        return conversation.id

    @DaoRel
    async def delete(self, conversation_id: str, session: AsyncSession | None = None):
        """删除指定对话

        :param conversation_id: 对话ID
        :param session: 可选数据库会话
        :raises: ValueError 对话不存在时抛出
        """
        conv = await session.get(Conversation, conversation_id)
        if not conv:
            raise ValueError(f"未找到ID为 {conversation_id} 的对话")
        await session.delete(conv)
        await session.flush()

    @DaoRel
    async def update(
        self,
        conversation_id: str,
        data: ConversationUpdate,
        session: AsyncSession | None = None,
    ):
        """更新指定对话(仅更新传入字段)

        :param conversation_id: 对话ID
        :param data: 对话更新数据
        :param session: 可选数据库会话
        :raises: ValueError 对话不存在时抛出
        """
        update_data = data.model_dump(exclude_unset=True)
        stmt = (
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(**update_data)
        )
        result = await session.exec(stmt)
        if result.rowcount == 0:
            raise ValueError(f"未找到ID为 {conversation_id} 的对话")
        await session.flush()

    @DaoRel
    async def get(
        self, conversation_id: str, session: AsyncSession | None = None
    ) -> Conversation | None:
        """查询单个对话

        :param conversation_id: 对话ID
        :param session: 可选数据库会话
        :return: 对话对象,未找到返回None
        """
        return await session.get(Conversation, conversation_id)

    @DaoRel
    async def list_by_user(
        self,
        user_id: str,
        offset: int,
        limit: int,
        session: AsyncSession | None = None,
    ) -> list[Conversation]:
        """按用户ID查询对话列表(按更新时间倒序)

        :param user_id: 用户ID
        :param offset: 偏移量
        :param limit: 单页数量
        :param session: 可选数据库会话
        :return: 对话列表
        """
        statement = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def count_by_user(
        self, user_id: str, session: AsyncSession | None = None
    ) -> int:
        """统计指定用户的对话总数

        :param user_id: 用户ID
        :param session: 可选数据库会话
        :return: 对话数量
        """
        statement = (
            select(func.count())
            .select_from(Conversation)
            .where(Conversation.user_id == user_id)
        )
        result = await session.exec(statement)
        return result.one()
