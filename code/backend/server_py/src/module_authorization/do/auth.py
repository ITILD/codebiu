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


class RegisterRequest(BaseModel):
    """注册请求模型(相比用户创建数据增加邮箱验证码字段)"""
    username: str = Field(..., max_length=50, description="用户名")
    password: str = Field(..., max_length=255, description="密码")
    email: str | None = Field(default=None, max_length=100, description="邮箱")
    phone: str | None = Field(default=None, max_length=20, description="电话号码")
    nickname: str | None = Field(default=None, max_length=50, description="昵称")
    code: str | None = Field(
        default=None, max_length=10, description="邮箱验证码(开启注册邮箱验证时必填)"
    )


class RegisterCodeRequest(BaseModel):
    """注册邮箱验证码发送请求模型"""
    email: str = Field(..., max_length=100, description="接收验证码的邮箱")


class RegisterConfigResponse(BaseModel):
    """注册流程配置响应模型(前端据此决定是否展示验证码输入)"""
    email_verify: bool = Field(default=False, description="注册是否需要邮箱验证码")
    
