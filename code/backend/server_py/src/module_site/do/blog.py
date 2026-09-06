"""博客文章数据模型: 在线 markdown 编辑 或 关联 URL 两种发布来源"""
from uuid import uuid4
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SAEnum, Text
from sqlmodel import Field, SQLModel


# 发布来源: markdown 在线编辑 / url 关联外链
class PostSource(str, Enum):
    Markdown = "markdown"
    Url = "url"


# 发布状态: 草稿 / 已发布
class PostStatus(str, Enum):
    Draft = "draft"
    Published = "published"


def _enum(col_cls: type[Enum], length: int) -> SAEnum:
    """VARCHAR 存储的枚举列(避免 PG 原生枚举与旧数据类型冲突)"""
    return SAEnum(
        col_cls, native_enum=False, length=length,
        values_callable=lambda e: [m.value for m in e],
    )


class BlogPostBase(SQLModel):
    """博客文章基础模型(不含数据库表配置)"""

    title: str = Field(max_length=200, description="文章标题")
    source_type: PostSource = Field(
        default=PostSource.Markdown,
        sa_type=_enum(PostSource, 16),
        description="发布来源: markdown=在线编辑 / url=关联外链",
    )
    content: str = Field(
        default="", sa_column=Column(Text),
        description="markdown 正文(source_type=url 时可空)",
    )
    url: str | None = Field(
        default=None, max_length=1000, description="关联博客外链地址(source_type=url 时必填)"
    )
    category: str | None = Field(default=None, max_length=50, description="分类标签")
    status: PostStatus = Field(
        default=PostStatus.Draft,
        sa_type=_enum(PostStatus, 16),
        description="发布状态: draft=草稿 / published=已发布",
    )


class BlogPost(BlogPostBase, table=True):
    """博客文章数据库模型(对应数据库表)"""

    __tablename__ = "blog_post"

    id: str = Field(
        default_factory=lambda: uuid4().hex,
        primary_key=True,
        index=True,
        description="唯一标识符",
    )
    user_id: str = Field(index=True, description="作者用户ID(归属隔离)")
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


class BlogPostCreate(BlogPostBase):
    """创建博客文章的请求模型"""


class BlogPostUpdate(SQLModel):
    """更新博客文章的请求模型(全部可选, 仅更新传入字段)"""

    title: str | None = Field(default=None, max_length=200)
    source_type: PostSource | None = Field(default=None, sa_type=_enum(PostSource, 16))
    content: str | None = Field(default=None, sa_column=Column(Text))
    url: str | None = Field(default=None, max_length=1000)
    category: str | None = Field(default=None, max_length=50)
    status: PostStatus | None = Field(default=None, sa_type=_enum(PostStatus, 16))
