from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_rag.do.chat_message import ChatMessage, ChatMessageCreate, ChatMessageResponse
from module_rag.dao.chat_message import ChatMessageDao
from langchain_core.messages import BaseMessage
from module_rag.config.checkpointer import get_checkpointer

class ChatMessageService:
    """聊天消息服务"""

    def __init__(self, chat_message_dao: ChatMessageDao | None = None):
        self.chat_message_dao = chat_message_dao or ChatMessageDao()

    async def add(self, message: ChatMessageCreate) -> str:
        """添加聊天消息"""
        return await self.chat_message_dao.add(message)

    async def list_by_conversation(
        self, conversation_id: str, pagination: PaginationParams | None = None
    ) -> PaginationResponse:
        """获取对话的消息列表"""
        offset = pagination.offset if pagination else 0
        limit = pagination.limit if pagination else 1000
        items = await self.chat_message_dao.list_by_conversation(
            conversation_id, offset, limit
        )
        total = await self.chat_message_dao.count_by_conversation(conversation_id)
        if pagination:
            return PaginationResponse.create(items, total, pagination)
        return PaginationResponse.create(items, total, PaginationParams(page=1, size=limit))


    async def _get_history_from_checkpointer( self, conversation_id: str) -> list[BaseMessage]:
        """从检查点获取对话历史消息"""
        """
        从 LangGraph Checkpointer 获取完整的历史消息状态
        :param checkpointer: PostgreSQL 异步检查点实例
        :param conversation_id: 会话唯一标识 (thread_id)
        :return: 包含历史上下文的 BaseMessage 列表
        """
        config = {"configurable": {"thread_id": conversation_id}}

        # 获取该 thread 的最新状态元组 (CheckpointTuple)
        # 注意：alist 返回 async generator 不能 await，用 aget_tuple 获取最新一条
        checkpointer = await get_checkpointer()
        state_tuple = await checkpointer.aget_tuple(config)

        if state_tuple and state_tuple.checkpoint:
            # state_tuple.checkpoint 是 dict，包含 channel_values
            channel_values = state_tuple.checkpoint.get("channel_values", {})
            return channel_values.get("messages", [])

        return []

if __name__ == "__main__":
    async def test():
        service = ChatMessageService()
        history = await service._get_history_from_checkpointer("123")
        print(history)
    import asyncio
    asyncio.run(test())
