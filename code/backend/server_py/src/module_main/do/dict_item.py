from sqlmodel import Column, DateTime, Field, SQLModel
from uuid import uuid4
from datetime import datetime, timezone


class DictItemBase(SQLModel):
    """
    字典项基础模型(不含数据库表配置)
    """
    dict_type_id: str = Field(description="字典类型ID")
    item_code: str = Field(max_length=50, description="字典项编码")
    item_name: str = Field(max_length=100, description="字典项名称")
    item_value: str | None = Field(default=None, max_length=200, description="字典项值")
    description: str | None = Field(default=None, max_length=500, description="字典项描述")
    is_active: bool = Field(default=True, description="是否激活状态")
    sort_order: int = Field(default=0, description="排序顺序")


class DictItem(DictItemBase, table=True):
    """
    字典项数据库模型(对应数据库表)
    """
    __tablename__ = "dict_item"

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


class DictItemCreate(DictItemBase):
    """
    创建字典项的请求模型
    """
    pass


class DictItemUpdate(DictItemBase):
    """
    更新字典项的请求模型
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