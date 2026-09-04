from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func
from common.config.db import DaoRel
from module_rag.do.chat_message import ChatMessage, ChatMessageCreate


class ChatMessageDao:
    """聊天消息数据访问对象"""

    @DaoRel
    async def add(
        self, message: ChatMessageCreate, session: AsyncSession | None = None
    ) -> str:
        """新增聊天消息记录

        :param message: 聊天消息创建数据
        :param session: 可选数据库会话(事务内复用)
        :return: 新建消息的ID
        """
        db_message = ChatMessage.model_validate(message.model_dump())
        session.add(db_message)
        await session.flush()
        return db_message.id

    @DaoRel
    async def list_by_conversation(
        self,
        conversation_id: str,
        offset: int = 0,
        limit: int = 1000,
        session: AsyncSession | None = None,
    ) -> list[ChatMessage]:
        """按对话ID查询消息列表(按创建时间升序)

        :param conversation_id: 对话ID
        :param offset: 偏移量
        :param limit: 单页数量上限
        :param session: 可选数据库会话
        :return: 消息列表
        """
        statement = (
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def count_by_conversation(
        self, conversation_id: str, session: AsyncSession | None = None
    ) -> int:
        """统计指定对话的消息总数

        :param conversation_id: 对话ID
        :param session: 可选数据库会话
        :return: 消息数量
        """
        statement = (
            select(func.count())
            .select_from(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
        )
        result = await session.exec(statement)
        return result.one()

    @DaoRel
    async def delete_by_conversation(
        self, conversation_id: str, session: AsyncSession | None = None
    ):
        """删除指定对话下的全部消息

        :param conversation_id: 对话ID
        :param session: 可选数据库会话
        """
        messages = await session.exec(
            select(ChatMessage).where(ChatMessage.conversation_id == conversation_id)
        )
        for msg in messages.all():
            await session.delete(msg)
        await session.flush()
