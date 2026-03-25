from sqlmodel import Column, DateTime, Field, SQLModel
from uuid import uuid4
from datetime import datetime, timezone
from pydantic import BaseModel

class SynonymGroupBase(SQLModel):
    """
    同义词组基础模型(不含数据库表配置)
    """
    pid: str = Field(description="项目ID")
    name: str = Field(max_length=100, description="同义词组名称")
    description: str | None = Field(
        default=None, max_length=500, description="同义词组描述"
    )
    is_active: bool | None = Field(default=True, description="是否激活状态")


class SynonymGroup(SynonymGroupBase, table=True):
    """
    同义词组数据库模型(对应数据库表)
    """
    __tablename__ = "synonym_group"
    
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


class SynonymGroupCreate(SynonymGroupBase):
    """
    创建同义词组的请求模型
    """
    pass


class SynonymGroupUpdate(SynonymGroupBase):
    """
    更新同义词组的请求模型
    """

class SynonymGroupBatchDelete(SQLModel):
    """
    批量删除同义词组的请求模型
    """
    ids: list[str] = Field(description="要删除的同义词组ID列表", min_length=1, max_length=200)


class SynonymBase(SQLModel):
    """
    单个同义词基础模型(不含数据库表配置)
    """
    pid: str = Field(description="项目ID")
    group_id: str = Field(description="所属同义词组ID")
    word: str = Field(max_length=100, description="同义词内容")
    language: str | None = Field(default=None, max_length=10, description="语言代码")


class Synonym(SynonymBase, table=True):
    """
    单个同义词数据库模型(对应数据库表)
    """
    __tablename__ = "synonym"
    
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


class SynonymCreate(SynonymBase):
    """
    创建同义词的请求模型
    """
    pass


class SynonymBatchCreate(BaseModel):
    """
    批量创建同义词的请求模型
    """
    pid: str = Field(description="项目ID")
    group_id: str = Field(description="所属同义词组ID")
    words: list[str] = Field(description="同义词列表", min_length=1, max_length=200)
    language: str | None = Field(default=None, max_length=10, description="语言代码")


class SynonymBatchDelete(BaseModel):
    """
    批量删除同义词的请求模型
    """
    ids: list[str] = Field(description="要删除的同义词ID列表", min_length=1, max_length=200)


class SynonymBatchSearch(BaseModel):
    """
    批量搜索同义词的请求模型
    """
    words: list[str] = Field(description="要搜索的词语列表", min_length=1, max_length=200)
    language: str | None = Field(default=None, max_length=10, description="语言代码(可选)")


class SynonymBatchSearchResult(BaseModel):
    """
    批量搜索同义词的响应模型
    """
    words: list[str] = Field(description="搜索的词,搜索词里的同义词也要返回")
    synonyms: list[str] = Field(description="该词语所在同义词组的所有同义词列表")


class SynonymBatchUpdate(BaseModel):
    """
    批量更新同义词的请求模型
    """
    pid: str = Field(description="项目ID")
    words: list[str] = Field(description="同义词列表", min_length=1, max_length=200)
    language: str | None = Field(default=None, max_length=10, description="语言代码")