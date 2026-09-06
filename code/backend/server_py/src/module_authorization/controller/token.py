from fastapi import APIRouter, Depends, HTTPException, status
import jwt
from fastapi import Request

from common.utils.fastapiEX.exceptions import NotFoundError, BusinessError
from module_authorization.config.server import module_app
from module_authorization.dependencies.token import get_token_service
from module_authorization.service.token import TokenService
from module_authorization.do.token import TokenCreateRequest,RefreshTokenRequest,RevokeTokenRequest
router = APIRouter()


def _token_access_from_query(request: Request) -> str | None:
    """从查询参数提取访问令牌(Request 依赖,FastAPI 不会误解析 lambda 形参)"""
    return request.query_params.get("token_access")


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
    return await service.create_token(request)


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
    # 刷新令牌无效等校验失败抛 ValueError, 由全局处理器映射为 400
    return await service.token_refresh(request.token_refresh)


@router.post(
    "/verify", 
    summary="验证令牌"
)
async def verify_token(
    token_access: str | None = Depends(_token_access_from_query),
    service: TokenService = Depends(get_token_service),
):
    """
    验证访问令牌的有效性
    
    - **token_access**: 要验证的访问令牌(通过查询参数传递)
    
    返回令牌中的有效载荷数据
    """
    if not token_access:
        raise BusinessError("Missing token_access parameter")

    try:
        payload = await service.verify_token(token_access)
        return {
            "valid": True,
            "payload": payload
        }
    except jwt.InvalidTokenError as e:
        # 令牌无效 -> 401; 保留 HTTPException 以携带 WWW-Authenticate 响应头
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )



@router.delete(
    "/revoke-all/{user_id}",
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
    await service.revoke_all_tokens_by_user(user_id)
    return {"success": True}


@router.get(
    "/info", 
    summary="获取令牌信息"
)
async def get_token_info(
    token_access: str | None = Depends(_token_access_from_query),
    service: TokenService = Depends(get_token_service),
):
    """
    获取令牌的详细信息
    
    - **token_access**: 访问令牌(通过查询参数传递)
    
    返回令牌在数据库中的完整信息
    """
    if not token_access:
        raise BusinessError("Missing token_access parameter")

    try:
        # 先解码令牌提取用户ID
        payload = await service.verify_token(token_access)
    except jwt.InvalidTokenError as e:
        # 令牌无效 -> 401; 保留 HTTPException 以携带 WWW-Authenticate 响应头
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user_id = payload.get("sub")
    if not user_id:
        # 保留 HTTPException 以携带 WWW-Authenticate 响应头
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing 'sub'",
            headers={"WWW-Authenticate": "Bearer"}
        )
    # 再查数据库中的令牌记录
    token_info = await service.get_token_by_user_id(user_id)
    if not token_info:
        raise NotFoundError("令牌不存在")
    return token_info


# 将路由器挂载到模块应用
module_app.include_router(router, prefix="/tokens", tags=["刷新令牌管理"])