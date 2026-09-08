from sqlmodel import Column, DateTime, Field, SQLModel
from uuid import uuid4
from datetime import datetime, timezone


class AgentBase(SQLModel):
    """智能体基础模型"""

    name: str = Field(..., max_length=100, description="智能体名称")
    description: str = Field(default="", max_length=500, description="智能体描述")
    system_prompt: str = Field(..., description="系统提示词(agent 人设与行为规则)")
    is_public: bool = Field(default=False, description="是否公共(所有用户可用)")
    is_builtin: bool = Field(default=False, description="是否内置种子(启动时幂等写入, 仅管理员可改)")


class Agent(AgentBase, table=True):
    """智能体数据库模型"""

    __tablename__ = "agent"

    id: str = Field(
        default_factory=lambda: uuid4().hex,
        primary_key=True,
        index=True,
        description="唯一标识符",
    )
    created_by: str | None = Field(
        default=None, max_length=50, index=True, description="创建者用户ID(内置为空)"
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


class AgentCreate(SQLModel):
    """创建智能体的请求模型(动态添加简单 agent: 名称+描述+提示词)"""

    name: str = Field(..., max_length=100, description="智能体名称")
    description: str = Field(default="", max_length=500, description="智能体描述")
    system_prompt: str = Field(..., min_length=1, description="系统提示词")


class AgentUpdate(SQLModel):
    """更新智能体的请求模型(归属/内置标记不可改)"""

    name: str | None = Field(None, max_length=100, description="智能体名称")
    description: str | None = Field(None, max_length=500, description="智能体描述")
    system_prompt: str | None = Field(None, min_length=1, description="系统提示词")
