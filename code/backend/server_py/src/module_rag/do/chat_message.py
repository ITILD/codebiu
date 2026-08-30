from sqlmodel import Column, DateTime, Field, SQLModel, JSON
from uuid import uuid4
from datetime import datetime, timezone

from module_ai.utils.llm.do.llm_type import RoleType


class ChatMessageBase(SQLModel):
    """聊天消息基础模型"""

    conversation_id: str = Field(..., max_length=50, index=True, description="所属对话ID")
    role: RoleType = Field(RoleType.USER, description="消息角色(user/assistant/system)")
    content: str = Field(..., description="消息内容")


class ChatMessage(ChatMessageBase, table=True):
    """聊天消息数据库模型"""

    __tablename__ = "chat_message"

    id: str = Field(
        default_factory=lambda: uuid4().hex,
        primary_key=True,
        index=True,
        description="唯一标识符",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
        description="创建时间",
    )
    blocks: list | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="非正式回答的过程区块(思考/检索等)，JSON 存储，用于前端折叠区恢复显示",
    )


class ChatMessageCreate(ChatMessageBase):
    """创建聊天消息的内部请求模型"""

    blocks: list | None = Field(default=None, description="过程区块(思考/检索等)")


class ChatMessageResponse(SQLModel):
    """聊天消息响应模型"""

    id: str = Field(..., description="唯一标识符")
    conversation_id: str = Field(..., description="所属对话ID")
    role: RoleType = Field(RoleType.USER, description="消息角色")
    content: str = Field(..., description="消息内容")
    created_at: datetime = Field(..., description="创建时间")
    blocks: list | None = Field(default=None, description="过程区块(思考/检索等)")
