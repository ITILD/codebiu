"""
模板字符串数据模型
基于string.Template的模板管理
"""

from sqlmodel import Column, DateTime, Field, SQLModel, JSON
from uuid import uuid4
from datetime import datetime, timezone


class TemplateStringBase(SQLModel):
    """
    模板字符串基础模型
    """

    name: str = Field(max_length=100, description="模板名称")
    description: str | None = Field(
        default=None, max_length=500, description="模板描述"
    )
    template_content: str = Field(description="模板内容，支持${variable}格式")
    category: str | None = Field(default=None, max_length=50, description="模板分类")
    tags: list[str] | None = Field(
        default_factory=list,
        sa_column=Column(JSON),  # ✅ 使用 JSON 类型
    )
    is_active: bool = Field(default=True, description="是否激活状态")


class TemplateString(TemplateStringBase, table=True):
    """
    模板字符串数据库模型
    """

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


class TemplateStringCreate(TemplateStringBase):
    """
    创建模板字符串的请求模型
    """
    pass


class TemplateStringUpdate(TemplateStringBase):
    """
    更新模板字符串的请求模型
    """

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            onupdate=lambda: datetime.now(timezone.utc),
            nullable=False,
        ),
        description="最后更新时间",
    )


class TemplateRenderRequest(SQLModel):
    """
    模板渲染请求模型
    """

    template_id: str | None = Field(
        default=None, description="模板ID，如果提供则使用数据库中的模板"
    )
    template_content: str | None = Field(default=None, description="直接提供的模板内容")
    variables: dict[str, str] = Field(default_factory=dict, description="模板变量字典")


class TemplateRenderResponse(SQLModel):
    """
    模板渲染响应模型
    """

    rendered_content: str = Field(description="渲染后的内容")
    template_id: str | None = Field(default=None, description="使用的模板ID")
    variables_used: list[str] = Field(description="使用的变量列表")
    variables_missing: list[str] = Field(description="缺失的变量列表")
