from fastapi import APIRouter, Depends, HTTPException, status
import jwt

from module_authorization.config.server import module_app
from module_authorization.dependencies.token import get_token_service
from module_authorization.service.token import TokenService
from module_authorization.do.token import TokenCreateRequest,RefreshTokenRequest,RevokeTokenRequest
router = APIRouter()

@router.post(
    "/create", 
    summary="创建令牌", 
    status_code=status.HTTP_201_CREATED
)
async def create_token(
    request:TokenCreateRequest,
    service:TokenService = Depends(get_token_service)
):
    """
    创建新的访问令牌和刷新令牌
    
    - **user_id**: 用户唯一标识
    - **username**: 用户名
    - **additional_data**: 可选的附加数据，将被包含在令牌中
    
    返回包含访问令牌、刷新令牌和过期信息的Token对象
    """
    try:
        return await service.create_token(request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post(
    "/refresh", 
    summary="刷新访问令牌"
)
async def token_refresh(
    request:RefreshTokenRequest,
    service:TokenService = Depends(get_token_service)
):
    """
    使用刷新令牌获取新的访问令牌
    
    - **token_refresh**: 有效的刷新令牌
    
    返回包含新的访问令牌和刷新令牌的Token对象
    """
    try:
        return await service.token_refresh(request.token_refresh)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post(
    "/verify", 
    summary="验证令牌"
)
async def verify_token(
    token_access = Depends(lambda x: x.query_params.get("token_access")),
    service:TokenService = Depends(get_token_service)
):
    """
    验证访问令牌的有效性
    
    - **token_access**: 要验证的访问令牌(通过查询参数传递)
    
    返回令牌中的有效载荷数据
    """
    if not token_access:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing token_access parameter"
        )
    
    try:
        payload = await service.verify_token(token_access)
        return {
            "valid": True,
            "payload": payload
        }
    except jwt.JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )



@router.delete(
    "/revoke_all/{user_id}", 
    summary="撤销用户所有令牌"
)
async def revoke_all_tokens(
    user_id: str,
    service:TokenService = Depends(get_token_service)
):
    """
    撤销指定用户的所有令牌
    
    - **user_id**: 用户ID
    
    强制用户重新登录
    """
    try:
        await service.revoke_all_tokens_by_user(user_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/info", 
    summary="获取令牌信息"
)
async def get_token_info(
    token_access = Depends(lambda x: x.query_params.get("token_access")),
    service:TokenService = Depends(get_token_service)
):
    """
    获取令牌的详细信息
    
    - **token_access**: 访问令牌(通过查询参数传递)
    
    返回令牌在数据库中的完整信息
    """
    if not token_access:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing token_access parameter"
        )
    
    try:
        token_info = await service.get_token_by_user_id(token_access)
        if not token_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token not found"
            )
        return token_info
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# 将路由器挂载到模块应用
module_app.include_router(router, prefix="/token", tags=["刷新令牌管理"])