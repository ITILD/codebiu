from enum import StrEnum

from sqlalchemy import Column, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel
from uuid import uuid4
from datetime import datetime, timezone


class AgentIOType(StrEnum):
    """智能体输入/输出类型: str=纯字符串(默认), json=JSON 结构体"""

    STR = "str"
    JSON = "json"


class AgentType(StrEnum):
    """智能体类型: simple=简单(单次 LLM 调用, 默认), workflow=工作流(Vue Flow 图编排)"""

    SIMPLE = "simple"
    WORKFLOW = "workflow"


def _io_enum_column() -> SAEnum:
    """构造 IO 类型枚举列(VARCHAR 存储, 避免原生 PG 枚举与存量列冲突)"""
    return SAEnum(
        AgentIOType,
        native_enum=False,
        length=8,
        values_callable=lambda e: [m.value for m in e],
    )


def _type_enum_column() -> SAEnum:
    """构造智能体类型枚举列(VARCHAR 存储, 避免原生 PG 枚举与存量列冲突)"""
    return SAEnum(
        AgentType,
        native_enum=False,
        length=12,
        values_callable=lambda e: [m.value for m in e],
    )


class AgentBase(SQLModel):
    """智能体基础模型"""

    name: str = Field(..., max_length=100, description="智能体名称")
    description: str = Field(default="", max_length=500, description="智能体描述")
    system_prompt: str = Field(..., description="系统提示词(agent 人设与行为规则)")
    agent_type: AgentType = Field(
        default=AgentType.SIMPLE,
        sa_type=_type_enum_column(),
        description="智能体类型: simple=简单(默认), workflow=工作流",
    )
    workflow: dict | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
        description="工作流图(Vue Flow nodes/edges/viewport), agent_type=workflow 时使用",
    )
    input_type: AgentIOType = Field(
        default=AgentIOType.STR,
        sa_type=_io_enum_column(),
        description="输入类型: str=字符串(默认), json=JSON 结构体",
    )
    output_type: AgentIOType = Field(
        default=AgentIOType.STR,
        sa_type=_io_enum_column(),
        description="输出类型: str=字符串(默认), json=JSON 结构体",
    )
    input_schema: dict | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
        description="输入结构(JSON Schema), input_type=json 时可选提供",
    )
    output_schema: dict | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
        description="输出结构(JSON Schema), output_type=json 时可选提供(结构化输出约束)",
    )
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
    """创建智能体的请求模型(名称+描述+提示词, 可选类型与结构体配置)"""

    name: str = Field(..., max_length=100, description="智能体名称")
    description: str = Field(default="", max_length=500, description="智能体描述")
    system_prompt: str = Field(..., min_length=1, description="系统提示词")
    agent_type: AgentType = Field(
        default=AgentType.SIMPLE, description="智能体类型: simple=简单(默认), workflow=工作流"
    )
    input_type: AgentIOType = Field(
        default=AgentIOType.STR, description="输入类型: str=字符串(默认), json=JSON 结构体"
    )
    output_type: AgentIOType = Field(
        default=AgentIOType.STR, description="输出类型: str=字符串(默认), json=JSON 结构体"
    )
    input_schema: dict | None = Field(
        None, description="输入结构(JSON Schema), input_type=json 时可选提供"
    )
    output_schema: dict | None = Field(
        None, description="输出结构(JSON Schema), output_type=json 时可选提供"
    )


class AgentUpdate(SQLModel):
    """更新智能体的请求模型(归属/内置标记不可改, 类型/结构体/工作流字段可选更新)"""

    name: str | None = Field(None, max_length=100, description="智能体名称")
    description: str | None = Field(None, max_length=500, description="智能体描述")
    system_prompt: str | None = Field(None, min_length=1, description="系统提示词")
    agent_type: AgentType | None = Field(None, description="智能体类型")
    workflow: dict | None = Field(None, description="工作流图(Vue Flow nodes/edges)")
    input_type: AgentIOType | None = Field(None, description="输入类型")
    output_type: AgentIOType | None = Field(None, description="输出类型")
    input_schema: dict | None = Field(None, description="输入结构(JSON Schema)")
    output_schema: dict | None = Field(None, description="输出结构(JSON Schema)")


class AgentWorkflowSaveRequest(SQLModel):
    """保存工作流配置请求(切换智能体类型 + 保存工作流图, 保存前静态校验)"""

    agent_type: AgentType = Field(..., description="智能体类型: simple/workflow")
    workflow: dict | None = Field(
        None, description="工作流图(Vue Flow nodes/edges/viewport), agent_type=workflow 时必填"
    )
