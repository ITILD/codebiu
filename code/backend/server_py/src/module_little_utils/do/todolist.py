from sqlmodel import Column, DateTime, Field, SQLModel
from uuid import uuid4
from datetime import datetime, timezone
from enum import Enum


# 状态枚举
class TodoStatus(str, Enum):
    Todo = "todo"
    Done = "done"
    # 其他状态...
    # 暂停
    Pause = "pause"


class TodolistBase(SQLModel):
    """
    计划列表基础模型(不含数据库表配置)
    """

    pid: str | None = Field(None, description="父级ID")
    name: str | None = Field(max_length=100, description="计划列表名称")
    value: str = Field(default="", description="内容")

    description: str | None = Field(
        default=None, max_length=500, description="计划列表描述"
    )
    start_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
        description="开始",
    )
    end_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True)), description="结束"
    )

    status: TodoStatus = Field(default=TodoStatus.Todo, description="代办状态")


class Todolist(TodolistBase, table=True):
    """
    计划列表数据库模型(对应数据库表)
    """

    id: str = Field(
        default_factory=lambda: uuid4().hex,
        primary_key=True,  # 主键
        index=True,  # 索引
        description="唯一标识符",
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
            onupdate=lambda: datetime.now(timezone.utc),  # 自动更新
            nullable=False,  # 不允许为空
        ),
        description="最后更新时间",
    )


class TodolistCreate(TodolistBase):
    """
    创建计划列表的请求模型
    """

    pass


class TodolistUpdate(TodolistBase):
    """
    更新计划列表的请求模型
    """

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            onupdate=lambda: datetime.now(timezone.utc),  # 自动更新
            nullable=False,  # 不允许为空
        ),
        description="最后更新时间",
    )
