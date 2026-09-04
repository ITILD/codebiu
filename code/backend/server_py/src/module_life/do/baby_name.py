from sqlmodel import Column, DateTime, Field, SQLModel
from module_life.utils.baby_name.do.baby_name import GenderEnum, NameStyleEnum
from pydantic import field_validator
from uuid import uuid4
from datetime import datetime, timezone

class BabyNameBase(SQLModel):
    """
    宝宝名字基础模型(不含数据库表配置)
    """

    name: str = Field(max_length=50, description="宝宝名字")
    gender: GenderEnum = Field(description="性别")
    style: NameStyleEnum = Field(description="名字风格")
    meaning: str | None = Field(default=None, max_length=500, description="名字含义")
    pinyin: str | None = Field(default=None, max_length=100, description="拼音")
    stroke_count: int | None = Field(default=None, description="笔画数")
    is_lucky: bool | None = Field(default=True, description="是否吉利")
    popularity: int = Field(default=0, description="流行度评分")
    tags: str | None = Field(default=None, max_length=200, description="标签，逗号分隔")
    source: str | None = Field(default=None, max_length=100, description="来源")
    is_active: bool | None = Field(default=True, description="是否激活状态")

    @field_validator("name")
    @classmethod
    def validate_name_length(cls, v):
        """校验名字长度必须在1-10个字符之间"""
        if len(v) < 1 or len(v) > 10:
            raise ValueError("名字长度必须在1-10个字符之间")
        return v


class BabyName(BabyNameBase, table=True):
    """
    宝宝名字数据库模型(对应数据库表)
    """

    __tablename__ = "baby_name"

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


class BabyNameCreate(BabyNameBase):
    """
    宝宝名字创建模型
    """

    pass


class BabyNameUpdate(SQLModel):
    """
    宝宝名字更新模型
    """

    name: str | None = Field(None, max_length=50, description="宝宝名字")
    gender: GenderEnum | None = Field(None, description="性别")
    style: NameStyleEnum | None = Field(None, description="名字风格")
    meaning: str | None = Field(None, max_length=500, description="名字含义")
    pinyin: str | None = Field(None, max_length=100, description="拼音")
    stroke_count: int | None = Field(None, description="笔画数")
    is_lucky: bool | None = Field(None, description="是否吉利")
    popularity: int | None = Field(None, description="流行度评分")
    tags: str | None = Field(None, max_length=200, description="标签，逗号分隔")
    source: str | None = Field(None, max_length=100, description="来源")
    is_active: bool | None = Field(None, description="是否激活状态")


class BabyNameBatchDelete(SQLModel):
    """
    宝宝名字批量删除模型
    """

    ids: list[str] = Field(description="要删除的名字ID列表")
