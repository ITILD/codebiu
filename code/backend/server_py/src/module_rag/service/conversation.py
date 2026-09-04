from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_rag.do.conversation import (
    Conversation,
    ConversationCreate,
    ConversationUpdate
)
from module_rag.dao.conversation import ConversationDao
from module_rag.dao.chat_message import ChatMessageDao
from common.config.db import DaoRel
from sqlmodel.ext.asyncio.session import AsyncSession
from module_rag.config.checkpointer import get_checkpointer

class ConversationService:
    """对话管理服务"""

    def __init__(
        self,
        conversation_dao: ConversationDao | None = None,
        chat_message_dao: ChatMessageDao | None = None,
    ):
        """依赖注入构造器:初始化所需的数据访问对象"""
        self.conversation_dao = conversation_dao or ConversationDao()
        self.chat_message_dao = chat_message_dao or ChatMessageDao()

    async def create(self, user_id: str, data: ConversationCreate) -> str:
        """创建对话"""
        conv = Conversation(
            user_id=user_id,
            title=data.title,
            agent_id=data.agent_id,
            project_ids=data.project_ids,
        )
        return await self.conversation_dao.add(conv)

    @DaoRel
    async def delete(self, conversation_id: str, session: AsyncSession | None = None):
        """删除对话(同时删除关联消息; checkpointer 清理失败时降级为告警,不影响删除结果)"""
        await self.chat_message_dao.delete_by_conversation(conversation_id, session)
        await self.conversation_dao.delete(conversation_id, session)
        # TODO 统一事务
        try:
            checkpointer = await get_checkpointer()
            await checkpointer.adelete_thread(conversation_id)
        except Exception as e:
            # langgraph checkpointer 不可用(如 Windows ProactorEventLoop 下 psycopg 无法建连)
            # 时降级: 会话与消息已删除,残留的 checkpoint 数据无害,仅记录告警
            import logging

            logging.getLogger(__name__).warning(
                f"清理会话 checkpointer 失败(已降级) conversation_id={conversation_id}: {e}"
            )

    async def update(self, conversation_id: str, data: ConversationUpdate):
        """更新对话"""
        await self.conversation_dao.update(conversation_id, data)

    async def get(self, conversation_id: str) -> Conversation | None:
        """获取对话详情"""
        return await self.conversation_dao.get(conversation_id)

    async def list_by_user(
        self, user_id: str, pagination: PaginationParams
    ) -> PaginationResponse:
        """分页获取用户的对话列表"""
        items = await self.conversation_dao.list_by_user(
            user_id, pagination.offset, pagination.limit
        )
        total = await self.conversation_dao.count_by_user(user_id)
        return PaginationResponse.create(items, total, pagination)


if __name__ == "__main__":
    import asyncio
    async def test():
        # SELECT DISTINCT thread_id FROM "checkpoint_blobs";
        ids = ["85689c88433d425dbb958bde668ab5d7"]
        checkpointer = await get_checkpointer()
        for id in ids:
            await checkpointer.adelete_thread(id)   
        print("删除成功")
    asyncio.run(test())
