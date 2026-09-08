"""智能体对话管理控制器(复用 module_rag 的 conversation 表, 按 agent_id 隔离)

创建/详情/更新/删除/消息列表直接复用 /rag/conversations 系列接口
(ConversationCreate 已支持 agent_id); 本控制器仅补充智能体域的会话列表。
"""

from fastapi import APIRouter, Depends
from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_authorization.dependencies.permission import require_permission
from module_rag.service.conversation import ConversationService
from module_rag.dependencies.conversation import get_conversation_service
from module_agent.config.server import module_app

router = APIRouter()


@router.get("/my", summary="获取我的智能体对话列表", response_model=PaginationResponse)
async def list_my_agent_conversations(
    pagination: PaginationParams = Depends(),
    agent_id: str | None = None,
    current_user_id: str = Depends(require_permission("agent", "chat", "read")),
    service: ConversationService = Depends(get_conversation_service),
):
    """分页获取当前用户的智能体对话(仅 agent_id 非空的会话; 可按智能体过滤)"""
    return await service.list_by_user(
        current_user_id, pagination, scope="agent", agent_id=agent_id
    )


# 注册路由(挂在 /agent/conversations 前缀下)
module_app.include_router(router, prefix="/conversations", tags=["智能体对话管理"])
