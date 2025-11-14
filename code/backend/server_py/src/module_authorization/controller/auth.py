from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from module_authorization.do.token import (
    RefreshTokenRequest,
    TokenResponseFull,
    TokenResponseBase,
)
from module_authorization.config.server import module_app
from module_authorization.service.auth import AuthService
from module_authorization.dependencies.auth import (
    get_auth_service,
    get_current_user,
    get_current_user_id
)
from module_authorization.do.user import UserCreate,User
from module_authorization.do.auth import AuthResponse,AuthLogoutRequest

# 创建路由器
router = APIRouter()


@router.get("/me")
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.get("/me_id")
async def read_users_me_id(current_user_id: str = Depends(get_current_user_id)):
    return current_user_id


@router.post("/register", summary="注册用户")
async def register_user(
    token_create: UserCreate,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    """注册用户"""
    try:
        token_response = await auth_service.register(token_create)
        return token_response
    except Exception as e:
        # 服务器内部错误
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

@router.post("/login", summary="登录获取访问令牌")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    """登录获取访问令牌"""
    try:
        token_response = await auth_service.login(form_data.username, form_data.password)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return token_response

@router.post("/logout", summary="登出")
async def logout(
    logout_request: AuthLogoutRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> bool:
    """登出"""
    try:
        await auth_service.logout(logout_request)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return True

@router.post("/refresh", summary="刷新访问令牌")
async def refresh_access_token(
    refresh_token_request: RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponseBase:
    """刷新访问令牌"""
    try:
        token_response = await auth_service.token_refresh(refresh_token_request.token_refresh)
    except HTTPException as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return token_response

# 注册登录
module_app.include_router(router, prefix="/auth")
