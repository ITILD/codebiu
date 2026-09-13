"""智能体运行模型(结构化输入输出的一次性运行 + 运行历史持久化)"""

from typing import Any
from uuid import uuid4
from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

import json


class AgentRunRequest(BaseModel):
    """运行智能体请求

    - model_id: 模型配置ID或模型标识名称(复用 module_ai 的模型配置)
    - input: 运行输入, 类型须匹配 agent.input_type(str 字符串 / JSON 结构体)
    """

    model_id: str = Field(..., description="模型配置ID或模型标识名称")
    input: Any = Field(..., description="运行输入(字符串或 JSON 对象/数组)")

    @field_validator("input", mode="before")
    @classmethod
    def parse_input(cls, v: Any) -> Any:
        """字符串入参时先尝试解析为 JSON, 解析失败则按原字符串处理"""
        if isinstance(v, str):
            try:
                return json.loads(v.strip())
            except (json.JSONDecodeError, ValueError):
                return v
        return v


class AgentRunResponse(BaseModel):
    """运行智能体响应"""

    run_id: str = Field(..., description="本次运行记录ID(运行历史可回看)")
    result: Any = Field(
        ..., description="运行结果: output_type=str 时为字符串, json 时为结构化对象"
    )
    trace: list[dict] | None = Field(
        default=None, description="工作流节点执行轨迹(仅工作流智能体返回, 每节点输入/输出/耗时/状态)"
    )


class AgentRun(SQLModel, table=True):
    """智能体运行历史表(仅记录成功运行; 输入/输出统一以 JSONB 存储, 字符串存为 JSON 标量)"""

    __tablename__ = "agent_run"

    id: str = Field(
        default_factory=lambda: uuid4().hex,
        primary_key=True,
        index=True,
        description="唯一标识符",
    )
    agent_id: str = Field(..., max_length=50, index=True, description="智能体ID")
    user_id: str = Field(..., max_length=50, index=True, description="运行用户ID")
    model_id: str = Field(..., max_length=100, description="使用的模型配置ID")
    input: Any = Field(
        ...,
        sa_column=Column(JSONB, nullable=False),
        description="运行输入(JSONB: 字符串或结构化对象)",
    )
    output: Any = Field(
        ...,
        sa_column=Column(JSONB, nullable=False),
        description="运行输出(JSONB: 字符串或结构化对象)",
    )
    trace: dict | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
        description="工作流节点执行轨迹({'nodes': [...]}, 仅工作流智能体记录)",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
        description="运行时间",
    )


class AgentRunHistory(BaseModel):
    """运行历史条目(响应视图)"""

    id: str = Field(..., description="运行记录ID")
    agent_id: str = Field(..., description="智能体ID")
    model_id: str = Field(..., description="模型配置ID")
    input: Any = Field(..., description="运行输入")
    output: Any = Field(..., description="运行输出")
    trace: dict | None = Field(None, description="工作流节点执行轨迹(仅工作流智能体)")
    created_at: datetime = Field(..., description="运行时间")
