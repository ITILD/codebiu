from fastapi import APIRouter, status, Depends, Query
from common.utils.fastapiEX.exceptions import NotFoundError, UnauthorizedError
from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_authorization.do.user import User, UserCreate, UserUpdate, UserResponse
from module_authorization.service.user import UserService
from module_authorization.dependencies.user import get_user_service
from module_authorization.dependencies.permission import require_permission
from module_authorization.config.server import module_app

router = APIRouter()

@router.post(
    "", summary="创建用户", status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("sys", "user", "create"))],
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
    # 用户名重复等校验失败抛 ValueError, 由全局处理器映射为 400
    return await service.add(user)

@router.get(
    "/list", summary="分页查询用户列表", response_model=PaginationResponse,
    dependencies=[Depends(require_permission("sys", "user", "read"))],
)
async def list_users(
    pagination: PaginationParams = Depends(),
    username: str | None = Query(None, max_length=50, description="用户名模糊搜索"),
    nickname: str | None = Query(None, max_length=50, description="昵称模糊搜索"),
    is_active: bool | None = Query(None, description="状态过滤(true=启用/false=禁用)"),
    service: UserService = Depends(get_user_service)
):
    """
    分页查询用户列表(支持多字段过滤)
    :param pagination: 分页参数 (通过查询参数传递)
    :param username: 用户名模糊搜索
    :param nickname: 昵称模糊搜索
    :param is_active: 状态过滤(true=启用/false=禁用)
    :param service: 用户服务依赖注入
    :return: 分页响应结果
    """
    return await service.list_paged(
        pagination, username=username, nickname=nickname, is_active=is_active
    )

@router.get("/{user_id}", summary="获取单个用户",
    dependencies=[Depends(require_permission("sys", "user", "read"))])
async def get_user(
    user_id: str,
    service: UserService = Depends(get_user_service)
):
    """
    获取单个用户详情, 用户不存在时返回404
    :param user_id: 用户ID
    :param service: 用户服务依赖注入
    :return: 用户详情
    """
    result = await service.get(user_id)
    if not result:
        raise NotFoundError("用户不存在")
    return result

@router.delete(
    "/{user_id}", summary="删除用户", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("sys", "user", "delete"))],
)
async def delete_user(
    user_id: str,
    service: UserService = Depends(get_user_service)
):
    """
    按ID删除用户,用户不存在时报400(dao 层 not-found 抛 ValueError, 由全局处理器映射);成功返回204
    :param user_id: 用户ID
    :param service: 用户服务依赖注入
    """
    await service.delete(user_id)

@router.put(
    "/{user_id}", summary="更新用户", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("sys", "user", "update"))],
)
async def update_user(
    user_id: str,
    user: UserUpdate,
    service: UserService = Depends(get_user_service)
):
    """
    按ID部分更新用户字段(仅传传入的字段),密码字段传入时自动哈希存储
    用户不存在时报400,成功返回204
    :param user_id: 用户ID
    :param user: 用户数据
    :param service: 用户服务依赖注入
    """
    await service.update(user_id, user)

@router.post("/authenticate", summary="用户认证", response_model=User)
async def authenticate_user(
    username: str,
    password: str,
    service: UserService = Depends(get_user_service)
):
    """
    校验用户名与密码哈希完成认证:凭据错误返回401,成功返回用户信息
    注意用户名/密码经查询参数传递,请勿在日志或分享链接中泄露
    :param username: 用户名
    :param password: 密码
    :param service: 用户服务依赖注入
    :return: 认证成功的用户信息
    """
    user = await service.authenticate(username, password)
    if not user:
        # 凭据错误 -> 401
        raise UnauthorizedError("Invalid credentials")
    return user

# 注册路由
module_app.include_router(router, prefix="/users", tags=["用户管理"])