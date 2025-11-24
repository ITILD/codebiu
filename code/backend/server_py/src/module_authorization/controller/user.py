from fastapi import APIRouter, HTTPException, status, Depends
from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_authorization.do.user import User, UserCreate, UserUpdate, UserResponse
from module_authorization.service.user import UserService
from module_authorization.dependencies.user import get_user_service
from module_authorization.config.server import module_app

router = APIRouter()

@router.post(
    "", summary="创建用户", status_code=status.HTTP_201_CREATED, response_model=str
)
async def create_user(
    user: UserCreate,
    service: UserService = Depends(get_user_service)
)->UserResponse:
    """
    创建新用户
    :param user: 用户数据
    :param service: 用户服务依赖注入
    :return: 创建的用户ID
    """
    try:
        return await service.add(user)
    except Exception as e:
        # 服务器内部错误
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get(
    "/list", summary="分页查询用户列表", response_model=PaginationResponse
)
async def list_users(
    pagination: PaginationParams = Depends(),
    service: UserService = Depends(get_user_service)
):
    """
    分页查询用户列表
    :param pagination: 分页参数 (通过查询参数传递)
    :param service: 用户服务依赖注入
    :return: 分页响应结果
    """
    try:
        return await service.list_all(pagination)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

@router.get("/{user_id}", summary="获取单个用户", response_model=User)
async def get_user(
    user_id: str,
    service: UserService = Depends(get_user_service)
):
    """
    获取单个用户详情
    :param user_id: 用户ID
    :param service: 用户服务依赖注入
    :return: 用户详情
    """
    try:
        result = await service.get(user_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

@router.delete(
    "/{user_id}", summary="删除用户", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_user(
    user_id: str,
    service: UserService = Depends(get_user_service)
):
    """
    删除用户
    :param user_id: 用户ID
    :param service: 用户服务依赖注入
    """
    try:
        await service.delete(user_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

@router.put(
    "/{user_id}", summary="更新用户", status_code=status.HTTP_204_NO_CONTENT
)
async def update_user(
    user_id: str,
    user: UserUpdate,
    service: UserService = Depends(get_user_service)
):
    """
    更新用户
    :param user_id: 用户ID
    :param user: 用户数据
    :param service: 用户服务依赖注入
    """
    try:
        await service.update(user_id, user)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

@router.post("/authenticate", summary="用户认证", response_model=User)
async def authenticate_user(
    username: str,
    password: str,
    service: UserService = Depends(get_user_service)
):
    """
    用户认证
    :param username: 用户名
    :param password: 密码
    :param service: 用户服务依赖注入
    :return: 认证成功的用户信息
    """
    try:
        user = await service.authenticate(username, password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )
        return user
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

# 注册路由
module_app.include_router(router, prefix="/users", tags=["用户管理"])