from fastapi import APIRouter, HTTPException, status, Depends, Query
from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_authorization.do.role import Role, RoleCreate, RoleUpdate, RoleResponse
from module_authorization.service.role import RoleService
from module_authorization.dependencies.role import get_role_service
from module_authorization.dependencies.permission import require_permission
from module_authorization.config.server import module_app

router = APIRouter()

@router.post(
    "", summary="创建角色", status_code=status.HTTP_201_CREATED, response_model=str,
    dependencies=[Depends(require_permission("sys", "role", "create"))],
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
    "/list", summary="分页查询角色列表", response_model=PaginationResponse,
    dependencies=[Depends(require_permission("sys", "role", "read"))],
)
async def list_roles(
    pagination: PaginationParams = Depends(),
    name: str | None = Query(None, max_length=50, description="角色名称模糊搜索"),
    role_key: str | None = Query(None, max_length=100, description="权限字符模糊搜索"),
    is_active: bool | None = Query(None, description="状态过滤(true=启用/false=禁用)"),
    service: RoleService = Depends(get_role_service)
):
    """
    分页查询角色列表(支持多字段过滤)
    :param pagination: 分页参数
    :param name: 角色名称模糊搜索
    :param role_key: 权限字符模糊搜索
    :param is_active: 状态过滤(true=启用/false=禁用)
    """
    try:
        return await service.list_paged(
            pagination, name=name, role_key=role_key, is_active=is_active
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

@router.get("/all", summary="获取所有角色(不分页)",
    dependencies=[Depends(require_permission("sys", "role", "read"))])
async def list_all_roles(
    service: RoleService = Depends(get_role_service)
):
    """获取所有角色列表(不分页, 用于下拉选择)"""
    try:
        return await service.list_all()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

@router.get("/{role_id}", summary="获取单个角色", response_model=Role,
    dependencies=[Depends(require_permission("sys", "role", "read"))])
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

@router.delete(
    "/{role_id}", summary="删除角色", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("sys", "role", "delete"))],
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
    "/{role_id}", summary="更新角色", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("sys", "role", "update"))],
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

@router.get("/name/{name}", summary="通过名称获取角色", response_model=Role,
    dependencies=[Depends(require_permission("sys", "role", "read"))])
async def get_role_by_name(
    name: str,
    service: RoleService = Depends(get_role_service)
):
    """通过名称获取角色"""
    try:
        result = await service.get_by_name(name)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

@router.get("/key/{role_key}", summary="通过权限字符串获取角色", response_model=Role,
    dependencies=[Depends(require_permission("sys", "role", "read"))])
async def get_role_by_key(
    role_key: str,
    service: RoleService = Depends(get_role_service)
):
    """通过角色权限字符串获取角色"""
    try:
        result = await service.get_by_role_key(role_key)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

# 注册路由
module_app.include_router(router, prefix="/roles", tags=["角色管理"])