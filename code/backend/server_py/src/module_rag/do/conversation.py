from sqlmodel import Column, DateTime, Field, SQLModel, JSON
from uuid import uuid4
from datetime import datetime, timezone
from pydantic import BaseModel

class ConversationBase(SQLModel):
    """对话基础模型"""

    title: str = Field(..., max_length=200, description="对话标题")
    agent_id: str | None = Field(default=None, max_length=50, description="智能体ID(当前为空)")


class Conversation(ConversationBase, table=True):
    """对话数据库模型"""

    __tablename__ = "conversation"

    id: str = Field(
        default_factory=lambda: uuid4().hex,
        primary_key=True,
        index=True,
        description="唯一标识符",
    )
    user_id: str = Field(..., max_length=50, index=True, description="用户ID")
    project_ids: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
        description="关联知识库(项目)ID列表",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
        description="创建时间",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            onupdate=lambda: datetime.now(timezone.utc),
            nullable=False,
        ),
        description="最后更新时间",
    )


class ConversationCreate(SQLModel):
    """创建对话的请求模型"""

    title: str = Field(..., max_length=200, description="对话标题")
    agent_id: str | None = Field(default=None, max_length=50, description="智能体ID")
    project_ids: list[str] = Field(default_factory=list, description="关联知识库ID列表")


class ConversationUpdate(SQLModel):
    """更新对话的请求模型"""

    title: str | None = Field(None, max_length=200, description="对话标题")
    agent_id: str | None = Field(None, max_length=50, description="智能体ID")
    project_ids: list[str] | None = Field(None, description="关联知识库ID列表")


class ConversationResponse(SQLModel):
    """对话响应模型"""

    id: str = Field(..., description="唯一标识符")
    user_id: str = Field(..., description="用户ID")
    title: str = Field(..., description="对话标题")
    agent_id: str | None = Field(default=None, description="智能体ID")
    project_ids: list[str] = Field(default_factory=list, description="关联知识库ID列表")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="最后更新时间")


class ChatRequest(BaseModel):
    """聊天请求"""

    message: str
    project_ids: list[str] = []
    deep_thinking: bool = False
    rerank_limit: int = Field(default=20, description="Rerank精排返回的最大结果数") # 新增

class ConversationSummary(BaseModel):
    """对话摘要结构化模型"""
    title: str = Field(default="新对话", description="不超过20字的对话标题")
    summary: str = Field(default="", description="不超过100字的对话总结")

class SummaryState(dict):
    """总结节点的状态"""
    history_text: str
    summary: ConversationSummary | None = None