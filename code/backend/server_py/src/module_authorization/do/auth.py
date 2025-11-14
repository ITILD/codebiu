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
    
