from sqlmodel import Column, DateTime, Field, SQLModel
from uuid import uuid4
from datetime import datetime, timezone


class UserBase(SQLModel):
    """用户基础模型（不含数据库表配置）"""

    username: str = Field(..., max_length=50, description="用户名")
    password: str = Field(..., max_length=255, description="密码")
    email: str | None = Field( max_length=100, description="邮箱")
    phone: str | None = Field( max_length=20, description="电话号码")
    nickname: str | None = Field( max_length=50, description="昵称")
    avatar: str | None = Field(default=None, max_length=255, description="头像")
    is_active: bool = Field(default=True, description="是否激活")


class User(UserBase, table=True):
    """用户数据库模型（对应数据库表）"""

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


class UserCreate(UserBase):
    """创建用户的请求模型"""

    pass


class UserUpdate(SQLModel):
    """更新用户的请求模型"""

    username: str | None = Field(None, max_length=50, description="用户名")
    password: str | None = Field(None, max_length=255, description="密码")
    email: str | None = Field(None, max_length=100, description="邮箱")
    phone: str | None = Field(None, max_length=20, description="电话号码")
    nickname: str | None = Field(None, max_length=50, description="昵称")
    avatar: str | None = Field(None, max_length=255, description="头像")
    is_active: bool | None = Field(None, description="是否激活")


class UserResponse(SQLModel):
    """用户响应模型"""

    id: str = Field(..., description="唯一标识符")
    username: str = Field(..., description="用户名")
    email: str | None = Field( description="邮箱")
    phone: str | None = Field( description="电话号码")
    nickname: str | None = Field( description="昵称")
    avatar: str | None = Field( description="头像")
    is_active: bool = Field(default=True, description="是否激活")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="最后更新时间")
