from sqlmodel import Column, DateTime, Field, SQLModel
from uuid import uuid4
from datetime import datetime, timezone


class TemplateBase(SQLModel):
    """
    模板基础模型(不含数据库表配置)
    """

    pid: str | None = Field(None, description="父级ID")
    value: int = Field(default=0, description="数值字段")
    name: str | None = Field( max_length=100, description="模板名称")
    description: str | None = Field(
        default=None, max_length=500, description="模板描述"
    )
    is_active: bool | None = Field(default=True, description="是否激活状态")


class Template(TemplateBase, table=True):
    """
    模板数据库模型(对应数据库表)
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


class TemplateCreate(TemplateBase):
    """
    创建模板的请求模型
    """

    pass


class TemplateUpdate(TemplateBase):
    """
    更新模板的请求模型
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
