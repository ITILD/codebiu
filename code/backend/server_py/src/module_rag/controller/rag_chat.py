"""
RAG 聊天控制器
- 流式聊天(SSE)：从 conversation.py 迁移过来
- 对话总结：压缩历史消息并生成标题
"""

from fastapi import APIRouter, HTTPException, status, Depends, Request
from sse_starlette import EventSourceResponse
from module_rag.do.rag_chat import ConversationSummary
from module_rag.do.conversation import ChatRequest
from module_rag.service.rag_chat import RagChatService
from module_rag.dependencies.rag_chat import get_rag_chat_service_single
from module_authorization.dependencies.auth import get_current_user_id
from module_authorization.dependencies.permission import require_permission
from module_rag.config.server import module_app
from module_ai.utils.llm.response.sse import event_generator
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/{conversation_id}/chat", summary="流式聊天(SSE)")
async def chat_stream(
    conversation_id: str,
    chat_request: ChatRequest,
    request_obj: Request,
    current_user_id: str = Depends(require_permission("rag", "chat", "write")),
    rag_chat_service: RagChatService = Depends(get_rag_chat_service_single),
) -> EventSourceResponse:
    """
    流式聊天接口(SSE)
    - 根据对话ID获取上下文(langgraph postgres checkpointer)
    - 支持传入知识库列表，有内容时先做意图分析
    - 输出为流式 SSE
    """
    try:
        responses = rag_chat_service.chat_stream(
            conversation_id=conversation_id, user_id=current_user_id, chat_request=chat_request
        )
        return EventSourceResponse(
            event_generator(responses, request_obj), media_type="text/event-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post(
    "/{conversation_id}/summarize",
    summary="总结历史对话(压缩消息)并生成标题",
    response_model=ConversationSummary,
)
async def summarize_conversation(
    conversation_id: str,
    current_user_id: str = Depends(require_permission("rag", "chat", "write")),
    rag_chat_service: RagChatService = Depends(get_rag_chat_service_single),
):
    """
    总结历史对话(压缩消息)并生成标题
    - 从 checkpointer 拉取完整消息历史
    - 调用 LLM 生成对话摘要和简短标题
    - 持久化更新对话标题
    """
    try:
        result = await rag_chat_service.summarize_conversation(conversation_id, current_user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# 注册路由(挂在 /rag/rag-chat 前缀下)
module_app.include_router(router, prefix="/rag-chat", tags=["RAG聊天"])
