from sqlmodel import Column, DateTime, Field, SQLModel
from uuid import uuid4
from datetime import datetime, timezone


class UserModelBase(SQLModel):
    """用户-模型绑定基础模型(不含数据库表配置)"""

    user_id: str = Field(..., max_length=50, index=True, description="用户ID")
    chat_model_id: str | None = Field(default=None, max_length=50, description="对话模型配置ID")
    embedding_model_id: str | None = Field(
        default=None, max_length=50, description="向量化模型配置ID"
    )
    rerank_model_id: str | None = Field(
        default=None, max_length=50, description="Rerank模型配置ID"
    )


class UserModel(UserModelBase, table=True):
    """用户-模型绑定数据库模型(对应数据库表)"""

    __tablename__ = "user_model"

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


class UserModelUpdate(SQLModel):
    """更新用户-模型绑定的请求模型"""

    chat_model_id: str | None = Field(None, description="对话模型配置ID")
    embedding_model_id: str | None = Field(None, description="向量化模型配置ID")
    rerank_model_id: str | None = Field(None, description="Rerank模型配置ID")


class UserModelResponse(SQLModel):
    """用户-模型绑定响应模型"""

    id: str = Field(default="", description="唯一标识符")
    user_id: str = Field(..., description="用户ID")
    chat_model_id: str | None = Field(default=None, description="对话模型配置ID")
    embedding_model_id: str | None = Field(default=None, description="向量化模型配置ID")
    rerank_model_id: str | None = Field(default=None, description="Rerank模型配置ID")
    created_at: datetime | None = Field(default=None, description="创建时间")
    updated_at: datetime | None = Field(default=None, description="最后更新时间")
