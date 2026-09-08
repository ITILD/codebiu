from fastapi import Depends
import asyncio

from module_rag.service.chat_message import ChatMessageService
from module_rag.service.conversation import ConversationService
from module_rag.service.user_model import UserModelService
from module_rag.dependencies.conversation import (
    get_chat_message_service,
    get_conversation_service,
)
from module_rag.dependencies.user_model import get_user_model_service

from module_agent.service.agent import AgentService
from module_agent.service.agent_chat import AgentChatService


def get_agent_service() -> AgentService:
    """AgentService 工厂"""
    return AgentService()


# 模块级变量存储单例(AgentChatService 编译图开销大, 全局仅初始化一次)
_agent_chat_service_instance: AgentChatService | None = None
_service_init_lock = asyncio.Lock()


async def get_agent_chat_service_single(
    agent_service: AgentService = Depends(get_agent_service),
    user_model_service: UserModelService = Depends(get_user_model_service),
    chat_message_service: ChatMessageService = Depends(get_chat_message_service),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> AgentChatService:
    """AgentChatService 工厂(单例, 编译一次通用图)"""
    global _agent_chat_service_instance
    async with _service_init_lock:
        if _agent_chat_service_instance is None:
            _agent_chat_service_instance = AgentChatService(
                agent_service=agent_service,
                user_model_service=user_model_service,
                chat_message_service=chat_message_service,
                conversation_service=conversation_service,
            )
            await _agent_chat_service_instance._init_compiled_graph()
    return _agent_chat_service_instance
