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
        messages = await session.exec(
            select(ChatMessage).where(ChatMessage.conversation_id == conversation_id)
        )
        for msg in messages.all():
            await session.delete(msg)
        await session.flush()
