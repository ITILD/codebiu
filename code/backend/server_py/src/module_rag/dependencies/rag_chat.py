from fastapi import Depends
from module_ai.service.llm import LLMService
from module_rag.service.user_model import UserModelService
from module_rag.service.chat_message import ChatMessageService
from module_rag.service.conversation import ConversationService
from module_rag.service.rag_chat import RagChatService
from module_rag.dependencies.conversation import (
    get_chat_message_service,
    get_conversation_service,
)
from module_rag.dependencies.project_document_chunk import (
    get_project_document_chunk_service,
)
from module_rag.service.project_document_chunk import ProjectDocumentChunkService
from module_ai.dependencies.llm import get_llm_service
from module_rag.dependencies.user_model import get_user_model_service
import asyncio

# 模块级变量存储单例
_rag_chat_service_instance: RagChatService | None = None
# 初始化锁，防止并发创建多个 Service 实例
_service_init_lock = asyncio.Lock()


async def get_rag_chat_service_single(
    llm_service: LLMService = Depends(get_llm_service),
    user_model_service: UserModelService = Depends(get_user_model_service),
    chat_message_service: ChatMessageService = Depends(get_chat_message_service),
    project_document_chunk_service: ProjectDocumentChunkService = Depends(
        get_project_document_chunk_service
    ),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> RagChatService:
    """RagChatService 工厂"""
    global _rag_chat_service_instance
    async with _service_init_lock:
        if _rag_chat_service_instance is None:
            instance = RagChatService(
                llm_service=llm_service,
                user_model_service=user_model_service,
                chat_message_service=chat_message_service,
                project_document_chunk_service=project_document_chunk_service,
                conversation_service=conversation_service,
            )
            # 先编译图再落单例: 初始化失败/被取消(如建流前客户端断开触发请求取消)时
            # 不缓存半成品实例, 下次请求自动重试(否则 chat_compiled_graph 永久为 None,
            # 所有问答请求都会流式返回 astream_events AttributeError)
            await instance._init_compiled_graphs()
            _rag_chat_service_instance = instance
    return _rag_chat_service_instance
