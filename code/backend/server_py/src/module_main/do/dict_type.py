from sqlmodel import Column, DateTime, Field, SQLModel
from uuid import uuid4
from datetime import datetime, timezone


class DictTypeBase(SQLModel):
    """
    字典类型基础模型(不含数据库表配置)
    """
    type_code: str = Field(max_length=50, description="字典类型编码")
    type_name: str = Field(max_length=100, description="字典类型名称")
    description: str | None = Field(default=None, max_length=500, description="字典类型描述")
    is_active: bool = Field(default=True, description="是否激活状态")
    sort_order: int = Field(default=0, description="排序顺序")


class DictType(DictTypeBase, table=True):
    """
    字典类型数据库模型(对应数据库表)
    """
    __tablename__ = "dict_type"

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


class DictTypeCreate(DictTypeBase):
    """
    创建字典类型的请求模型
    """
    pass


class DictTypeUpdate(DictTypeBase):
    """
    更新字典类型的请求模型
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