from fastapi import APIRouter, HTTPException, status, Depends
from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_authorization.do.role import Role, RoleCreate, RoleUpdate, RoleResponse
from module_authorization.service.role import RoleService
from module_authorization.dependencies.role import get_role_service
from module_authorization.config.server import module_app

router = APIRouter()

@router.post(
    "", summary="创建角色", status_code=status.HTTP_201_CREATED, response_model=str
)
async def create_role(
    role: RoleCreate,
    service: RoleService = Depends(get_role_service)
):
    """
    创建新角色
    :param role: 角色数据
    :param service: 角色服务依赖注入
    :return: 创建的角色ID
    """
    try:
        return await service.add(role)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

@router.get(
    "/list", summary="分页查询角色列表", response_model=PaginationResponse
)
async def list_roles(
    pagination: PaginationParams = Depends(),
    service: RoleService = Depends(get_role_service)
):
    """
    分页查询角色列表
    :param pagination: 分页参数 (通过查询参数传递)
    :param service: 角色服务依赖注入
    :return: 分页响应结果
    """
    try:
        return await service.list(pagination)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

@router.get("/{role_id}", summary="获取单个角色", response_model=Role)
async def get_role(
    role_id: str,
    service: RoleService = Depends(get_role_service)
):
    """
    获取单个角色详情
    :param role_id: 角色ID
    :param service: 角色服务依赖注入
    :return: 角色详情
    """
    try:
        result = await service.get(role_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
            )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

@router.delete(
    "/{role_id}", summary="删除角色", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_role(
    role_id: str,
    service: RoleService = Depends(get_role_service)
):
    """
    删除角色
    :param role_id: 角色ID
    :param service: 角色服务依赖注入
    """
    try:
        await service.delete(role_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

@router.put(
    "/{role_id}", summary="更新角色", status_code=status.HTTP_204_NO_CONTENT
)
async def update_role(
    role_id: str,
    role: RoleUpdate,
    service: RoleService = Depends(get_role_service)
):
    """
    更新角色
    :param role_id: 角色ID
    :param role: 角色数据
    :param service: 角色服务依赖注入
    """
    try:
        await service.update(role_id, role)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

@router.get("/name/{name}", summary="通过名称获取角色", response_model=Role)
async def get_role_by_name(
    name: str,
    service: RoleService = Depends(get_role_service)
):
    """
    通过名称获取角色
    :param name: 角色名称
    :param service: 角色服务依赖注入
    :return: 角色详情
    """
    try:
        result = await service.get_by_name(name)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
            )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

# 注册路由
module_app.include_router(router, prefix="/roles", tags=["角色管理"])