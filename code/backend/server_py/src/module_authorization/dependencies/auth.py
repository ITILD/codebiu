from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from module_authorization.service.auth import AuthService
from module_authorization.service.user import UserService
from module_authorization.service.token import TokenService
from module_authorization.dependencies.user import get_user_service
from module_authorization.dependencies.token import get_token_service

# 不做业务验证：oauth2_scheme 不验证 Token 的有效性、过期时间或签名。它只负责“搬运”字符串。
# OAuth2 scheme(tokenUrl 指向 OAuth2 标准响应端点,Swagger Authorize 才能自动提取令牌)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/authorization/auth/_token")


async def get_auth_service(
    user_service: UserService = Depends(get_user_service),
    token_service: TokenService = Depends(get_token_service),
):
    """AuthService工厂函数"""
    return AuthService(user_service, token_service)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    auth_service: AuthService = Depends(get_auth_service),
):
    """获取当前用户"""
    try:
        return await auth_service.get_current_user(token)

    except Exception as e:
        # 捕获所有其他异常，确保错误信息能够传递给前端
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


async def get_current_user_id(
    token: str = Depends(oauth2_scheme),
    auth_service: AuthService = Depends(get_auth_service),
):
    """获取当前用户ID"""
    try:
        return await auth_service.get_current_user_id(token)
    except Exception as e:
        # 捕获所有其他异常，确保错误信息能够传递给前端
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
