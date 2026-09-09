"""智能体聊天控制器(SSE 流式对话, agent 由对话记录的 agent_id 决定)"""

import logging

from fastapi import APIRouter, Depends, Request
from sse_starlette import EventSourceResponse

from module_ai.utils.llm.stream.sse import event_generator
from module_authorization.dependencies.permission import require_permission
from module_agent.config.server import module_app
from module_agent.dependencies.agent import get_agent_chat_service_single
from module_agent.do.agent_chat import AgentChatRequest
from module_agent.service.agent_chat import AgentChatService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/{conversation_id}/chat", summary="智能体流式聊天(SSE)")
async def chat_stream(
    conversation_id: str,
    chat_request: AgentChatRequest,
    request_obj: Request,
    current_user_id: str = Depends(require_permission("agent", "chat", "write")),
    agent_chat_service: AgentChatService = Depends(get_agent_chat_service_single),
) -> EventSourceResponse:
    """
    智能体流式聊天接口(SSE)
    - 对话关联的 agent 的 system_prompt 动态注入通用图
    - 上下文历史由 langgraph postgres checkpointer 按 thread_id 管理
    - 事件协议与 RAG 聊天一致(ANSWER/LLM_THINKING/STATUS/ERROR)
    """
    # 不做 try/except 包装: 建流前的校验错误(BizError 等)由全局异常处理器映射状态码,
    # 流式体内的异常由 event_generator 转为 ERROR 事件推送
    responses = agent_chat_service.stream_chat(
        conversation_id=conversation_id, user_id=current_user_id, chat_request=chat_request
    )
    return EventSourceResponse(
        event_generator(responses, request_obj), media_type="text/event-stream"
    )


# 注册路由(挂在 /agent/agent-chat 前缀下)
module_app.include_router(router, prefix="/agent-chat", tags=["智能体聊天"])
