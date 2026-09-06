from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm
from module_authorization.do.token import (
    RefreshTokenRequest,
    TokenResponseFull,
    TokenResponseBase,
)
from module_authorization.config.server import module_app
from module_authorization.service.auth import AuthService
from module_authorization.service.avatar import AvatarService
from module_authorization.dependencies.auth import (
    get_auth_service,
    get_current_user,
    get_current_user_id
)
from module_authorization.dependencies.avatar import get_avatar_service
from module_authorization.do.user import UserCreate,User
from module_authorization.do.auth import AuthResponse,AuthLogoutRequest,SelfProfileUpdate,PasswordChange

# 创建路由器
router = APIRouter()


@router.get("/me", summary="获取当前登录用户信息")
async def get_me(current_user: User = Depends(get_current_user)):
    """根据访问令牌返回当前登录用户的完整信息"""
    return current_user

@router.get("/me-id", summary="获取当前登录用户ID")
async def get_me_id(current_user_id: str = Depends(get_current_user_id)):
    """根据访问令牌返回当前登录用户的ID(轻量级身份校验)"""
    return current_user_id


@router.put("/me", summary="自助更新个人资料")
async def update_my_profile(
    profile: SelfProfileUpdate,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    """当前登录用户修改自己的昵称/邮箱/电话/头像(无需管理员权限)"""
    try:
        return await auth_service.update_my_profile(current_user.id, profile)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put(
    "/me/password", summary="自助修改密码", status_code=status.HTTP_204_NO_CONTENT
)
async def change_my_password(
    password_change: PasswordChange,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    """当前登录用户修改自己的密码(需验证旧密码,成功后返回204)"""
    try:
        await auth_service.change_my_password(
            current_user.id,
            password_change.old_password,
            password_change.new_password,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/me/avatar", summary="上传当前用户头像")
async def upload_my_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    avatar_service: AvatarService = Depends(get_avatar_service),
):
    """
    上传当前登录用户的头像(登录即可,无需权限码)
    头像经统一文件服务存入虚拟目录 /用户头像/<用户ID>/ 下, 并自动清理旧头像条目;
    下载走 /file/filesystem/download/{entry_id}(avatar 来源允许匿名访问)
    :param file: 图片文件(png/jpg/jpeg/gif/webp/svg/bmp)
    :return: {"avatar": 下载路径, "entry_id": 文件条目ID}
    """
    try:
        return await avatar_service.upload_avatar(current_user.id, file)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/me-permissions", summary="获取当前用户的角色与权限码")
async def get_my_permissions(
    current_user_id: str = Depends(get_current_user_id),
    auth_service: AuthService = Depends(get_auth_service),
):
    """获取当前用户的角色(按域分组)与权限码列表(登录用户即可调用,仅能查看自己)"""
    return await auth_service.get_user_permission_info(current_user_id)


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


@router.post("/token", summary="OAuth2 标准登录(Swagger Authorize 专用) 调试使用")
async def login_for_oauth2(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    """
    OAuth2 Password 流程标准端点,供 Swagger UI "Authorize" 按钮使用
    响应为标准格式 {"access_token": ..., "token_type": "bearer"},
    Swagger 才能自动提取并携带令牌调用其他接口;前端请继续使用 /login
    """
    try:
        token_response = await auth_service.login(form_data.username, form_data.password)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return {
        "access_token": token_response.tokens.access.token,
        "token_type": "bearer",
    }

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
