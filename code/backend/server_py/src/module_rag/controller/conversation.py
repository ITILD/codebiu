from fastapi import APIRouter, HTTPException, status, Depends
from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from pydantic import field_validator
from module_rag.do.conversation import (
    Conversation,
    ConversationCreate,
    ConversationUpdate,
)
from module_rag.service.conversation import ConversationService
from module_rag.service.chat_message import ChatMessageService
from module_rag.dependencies.conversation import (
    get_conversation_service,
    get_chat_message_service,
)
from module_authorization.dependencies.auth import get_current_user_id
from module_rag.config.server import module_app
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", summary="创建对话", status_code=status.HTTP_201_CREATED, response_model=str)
async def create_conversation(
    data: ConversationCreate,
    current_user_id: str = Depends(get_current_user_id),
    service: ConversationService = Depends(get_conversation_service),
):
    """创建新对话"""
    try:
        return await service.create(current_user_id, data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/my", summary="获取我的对话列表", response_model=PaginationResponse)
async def list_my_conversations(
    pagination: PaginationParams = Depends(),
    current_user_id: str = Depends(get_current_user_id),
    service: ConversationService = Depends(get_conversation_service),
):
    """分页获取当前用户的对话列表"""
    try:
        return await service.list_by_user(current_user_id, pagination)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{conversation_id}", summary="获取对话详情", response_model=Conversation)
async def get_conversation(
    conversation_id: str,
    service: ConversationService = Depends(get_conversation_service),
):
    """获取对话详情"""
    try:
        result = await service.get(conversation_id)
        if not result:
            raise HTTPException(status_code=404, detail="对话未找到")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{conversation_id}", summary="更新对话", status_code=status.HTTP_204_NO_CONTENT)
async def update_conversation(
    conversation_id: str,
    data: ConversationUpdate,
    service: ConversationService = Depends(get_conversation_service),
):
    """更新对话(标题/智能体/知识库)"""
    try:
        await service.update(conversation_id, data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{conversation_id}", summary="删除对话", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    service: ConversationService = Depends(get_conversation_service),
):
    """删除对话(同时删除关联消息)"""
    try:
        await service.delete(conversation_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===================== 对话消息 =====================


class ChatMessagePaginationParams(PaginationParams):
    """聊天消息分页参数(允许更大的 size，因为聊天历史通常一次加载较多)"""

    @field_validator("size")
    @classmethod
    def validate_size(cls, v):
        if v < 1:
            raise ValueError("size 必须大于等于 1")
        if v > 1000:
            raise ValueError("size 不能超过 1000")
        return v


@router.get(
    "/{conversation_id}/messages",
    summary="获取对话消息列表",
    response_model=PaginationResponse,
)
async def list_messages(
    conversation_id: str,
    pagination: ChatMessagePaginationParams = Depends(),
    service: ChatMessageService = Depends(get_chat_message_service),
):
    """获取指定对话的聊天消息列表"""
    try:
        return await service.list_by_conversation(conversation_id, pagination)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 注：流式聊天接口(SSE)已迁移至 module_rag.controller.rag_chat
# 路径: POST /rag/rag-chat/{conversation_id}/chat


# 注册路由
module_app.include_router(router, prefix="/conversations", tags=["对话管理"])
