from module_authorization.do.token import TokenResponseFull
from module_authorization.do.user import UserResponse
from pydantic import BaseModel,Field


class AuthResponse(BaseModel):
    """
    认证响应模型
    同时返回两种令牌和用户信息
    """
    tokens: TokenResponseFull
    user: UserResponse
    message: str = "register success"
    
class AuthLogoutRequest(BaseModel):
    """
    登出请求模型
    包含访问令牌和刷新令牌
    """
    token_access: str = Field(..., description="访问令牌")
    token_refresh: str = Field(..., description="刷新令牌")
    token_refresh_id: str = Field(..., description="刷新令牌存储的ID")


class SelfProfileUpdate(BaseModel):
    """
    自助资料更新模型(用户修改自己的基础信息)
    仅开放展示类字段,用户名/激活状态等敏感字段不开放
    """
    nickname: str | None = Field(None, max_length=50, description="昵称")
    email: str | None = Field(None, max_length=100, description="邮箱")
    phone: str | None = Field(None, max_length=20, description="电话号码")
    avatar: str | None = Field(None, max_length=255, description="头像地址")


class PasswordChange(BaseModel):
    """修改密码请求模型(需验证旧密码)"""
    old_password: str = Field(..., min_length=1, description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=255, description="新密码(至少6位)")
    
