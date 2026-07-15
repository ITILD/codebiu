from sqlmodel import Column, DateTime, Field, SQLModel
from uuid import uuid4
from datetime import datetime, timezone
from typing import Optional


class DeptBase(SQLModel):
    """部门基础模型(不含数据库表配置)"""

    parent_id: str | None = Field(default="0", description="父部门ID, 0表示根部门")
    ancestors: str = Field(default="", max_length=500, description="祖级列表, 用逗号分隔")
    name: str = Field(..., max_length=50, description="部门名称")
    order_num: int = Field(default=0, description="显示顺序")
    leader: str | None = Field(default=None, max_length=50, description="负责人")
    phone: str | None = Field(default=None, max_length=20, description="联系电话")
    email: str | None = Field(default=None, max_length=50, description="邮箱")
    is_active: bool = Field(default=True, description="是否启用")


class Dept(DeptBase, table=True):
    """部门数据库模型(对应数据库表)"""
    __tablename__ = "dept"

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
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            onupdate=lambda: datetime.now(timezone.utc),
            nullable=False,
        ),
        description="最后更新时间",
    )


class DeptCreate(DeptBase):
    """创建部门的请求模型"""
    pass


class DeptUpdate(SQLModel):
    """更新部门的请求模型"""

    parent_id: str | None = Field(None, description="父部门ID")
    ancestors: str | None = Field(None, description="祖级列表")
    name: str | None = Field(None, max_length=50, description="部门名称")
    order_num: int | None = Field(None, description="显示顺序")
    leader: str | None = Field(None, max_length=50, description="负责人")
    phone: str | None = Field(None, max_length=20, description="联系电话")
    email: str | None = Field(None, max_length=50, description="邮箱")
    is_active: bool | None = Field(None, description="是否启用")


class DeptResponse(DeptBase):
    """部门响应模型"""

    id: str = Field(..., description="唯一标识符")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="最后更新时间")


class DeptTree(SQLModel):
    """部门树形结构响应模型"""

    id: str = Field(..., description="唯一标识符")
    parent_id: str | None = Field(..., description="父部门ID")
    name: str = Field(..., description="部门名称")
    order_num: int = Field(..., description="显示顺序")
    leader: str | None = Field(None, description="负责人")
    phone: str | None = Field(None, description="联系电话")
    email: str | None = Field(None, description="邮箱")
    is_active: bool = Field(..., description="是否启用")
    children: list["DeptTree"] = Field(default_factory=list, description="子部门列表")
