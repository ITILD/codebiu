from pydantic import BaseModel
from sqlmodel import Column, DateTime, Field, SQLModel
from uuid import uuid4
from datetime import datetime, timezone
from common.utils.security.token_util import TokenType


class TokenBase(SQLModel):
    """令牌基础模型(不含数据库表配置)"""

    user_id: str = Field(..., description="用户ID")
    token: str = Field(..., description="访问令牌")
    token_type: TokenType = Field(default=TokenType.access, description="令牌类型")
    expires_in: int = Field(..., description="过期时间(秒)")
    expires_at: datetime = Field(..., description="过期时间")
    is_revoked: bool = Field(default=False, description="是否已撤销")


class Token(TokenBase, table=True):
    """令牌数据库模型(对应数据库表)"""

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


class TokenCreate(TokenBase):
    """创建令牌的请求模型"""

    pass


class TokenUpdate(TokenBase):
    """更新令牌的请求模型"""

    pass


class TokenResponseBase(BaseModel):
    """令牌响应基础模型"""

    token: str = Field(..., description="令牌")
    expires_in: int = Field(..., description="过期时间(秒)")
    token_id: str | None = Field(..., description="令牌存储的ID,只有刷新令牌有id")


class TokenResponseFull(SQLModel):
    """长期完整令牌响应模型"""

    access: TokenResponseBase = Field(..., description="访问令牌")
    refresh: TokenResponseBase = Field(..., description="刷新令牌")


# ############
class TokenCreateRequest(BaseModel):
    """创建令牌请求模型"""

    user_id: str = Field(..., description="用户ID")
    token_type: TokenType = Field(default=TokenType.access, description="令牌类型")
    additional_data: dict | None = Field(None, description="附加数据")


class RefreshTokenRequest(BaseModel):
    """刷新令牌请求模型"""

    token_refresh: str = Field(..., description="刷新令牌")


class RevokeTokenRequest(BaseModel):
    """撤销令牌请求模型"""

    token_access: str = Field(..., description="要撤销的访问令牌")


class RevokeUserTokensRequest(BaseModel):
    """撤销用户所有令牌请求模型"""

    user_id: str = Field(..., description="用户ID")
