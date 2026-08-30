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
        session.add(conversation)
        await session.flush()
        return conversation.id

    @DaoRel
    async def delete(self, conversation_id: str, session: AsyncSession | None = None):
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
        return await session.get(Conversation, conversation_id)

    @DaoRel
    async def list_by_user(
        self,
        user_id: str,
        offset: int,
        limit: int,
        session: AsyncSession | None = None,
    ) -> list[Conversation]:
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
        statement = (
            select(func.count())
            .select_from(Conversation)
            .where(Conversation.user_id == user_id)
        )
        result = await session.exec(statement)
        return result.one()
