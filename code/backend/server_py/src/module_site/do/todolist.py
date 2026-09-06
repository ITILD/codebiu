"""备忘数据模型(承接原 module_little_utils 的 todolist, 表名保持 todo_list 不变)"""
from uuid import uuid4
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SAEnum
from sqlmodel import Field, SQLModel


# 备忘状态: 待办 / 完成 / 暂停
class TodoStatus(str, Enum):
    Todo = "todo"
    Done = "done"
    Pause = "pause"


def _enum(col_cls: type[Enum], length: int) -> SAEnum:
    """VARCHAR 存储的枚举列(兼容存量 todo_list 表的 VARCHAR 数据)"""
    return SAEnum(
        col_cls, native_enum=False, length=length,
        values_callable=lambda e: [m.value for m in e],
    )


class TodolistBase(SQLModel):
    """备忘基础模型(不含数据库表配置)"""

    pid: str | None = Field(None, description="父级ID")
    name: str | None = Field(max_length=100, description="备忘标题")
    value: str = Field(default="", description="备忘全文内容")
    description: str | None = Field(
        default=None, max_length=500, description="备忘描述"
    )
    start_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
        description="备忘时间(日历展示依据)",
    )
    end_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True)), description="截止时间"
    )
    status: TodoStatus = Field(
        default=TodoStatus.Todo, sa_type=_enum(TodoStatus, 16), description="备忘状态"
    )


class Todolist(TodolistBase, table=True):
    """备忘数据库模型(对应数据库表)"""

    __tablename__ = "todo_list"

    id: str = Field(
        default_factory=lambda: uuid4().hex,
        primary_key=True,
        index=True,
        description="唯一标识符",
    )
    user_id: str | None = Field(
        default=None, index=True, description="归属用户ID(存量数据为 NULL)"
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


class TodolistCreate(SQLModel):
    """创建备忘的请求模型(归属由令牌解析, 不接受前端传入)"""

    name: str = Field(max_length=100, description="备忘标题")
    value: str = Field(default="", description="备忘全文内容")
    description: str | None = Field(default=None, max_length=500)
    start_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="备忘时间(日历展示依据)",
    )
    end_at: datetime | None = Field(default=None)
    status: TodoStatus = Field(default=TodoStatus.Todo)


class TodolistUpdate(SQLModel):
    """更新备忘的请求模型(全部可选, 仅更新传入字段)"""

    name: str | None = Field(default=None, max_length=100)
    value: str | None = Field(default=None)
    description: str | None = Field(default=None, max_length=500)
    start_at: datetime | None = Field(default=None)
    end_at: datetime | None = Field(default=None)
    status: TodoStatus | None = Field(default=None, sa_type=_enum(TodoStatus, 16))
