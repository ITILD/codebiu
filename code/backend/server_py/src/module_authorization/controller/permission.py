from fastapi import APIRouter, HTTPException, status, Depends
from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_authorization.do.permission import Permission, PermissionCreate, PermissionUpdate, PermissionResponse, PermissionTree
from module_authorization.service.permission import PermissionService
from module_authorization.dependencies.permission import get_permission_service
from module_authorization.config.server import module_app

router = APIRouter()

@router.post(
    "", summary="创建权限", status_code=status.HTTP_201_CREATED, response_model=str
)
async def create_permission(
    permission: PermissionCreate,
    service: PermissionService = Depends(get_permission_service)
):
    """创建新权限"""
    try:
        return await service.add(permission)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/tree", summary="获取权限树形结构", response_model=list[PermissionTree])
async def get_permission_tree(
    service: PermissionService = Depends(get_permission_service)
):
    """获取权限/菜单树形结构"""
    try:
        return await service.get_tree()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "/list", summary="分页查询权限列表", response_model=PaginationResponse
)
async def list_permissions(
    pagination: PaginationParams = Depends(),
    service: PermissionService = Depends(get_permission_service)
):
    """分页查询权限列表"""
    try:
        return await service.list_all(pagination)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/{permission_id}", summary="获取单个权限", response_model=Permission)
async def get_permission(
    permission_id: str,
    service: PermissionService = Depends(get_permission_service)
):
    """获取单个权限详情"""
    try:
        result = await service.get(permission_id)
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found")
        return result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete(
    "/{permission_id}", summary="删除权限", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_permission(
    permission_id: str,
    service: PermissionService = Depends(get_permission_service)
):
    """删除权限"""
    try:
        await service.delete(permission_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put(
    "/{permission_id}", summary="更新权限", status_code=status.HTTP_204_NO_CONTENT
)
async def update_permission(
    permission_id: str,
    permission: PermissionUpdate,
    service: PermissionService = Depends(get_permission_service)
):
    """更新权限"""
    try:
        await service.update(permission_id, permission)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/code/{code}", summary="通过代码获取权限", response_model=Permission)
async def get_permission_by_code(
    code: str,
    service: PermissionService = Depends(get_permission_service)
):
    """通过代码获取权限"""
    try:
        result = await service.get_by_code(code)
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found")
        return result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/parent/{parent_id}", summary="获取子权限列表")
async def get_permissions_by_parent_id(
    parent_id: str,
    service: PermissionService = Depends(get_permission_service)
):
    """获取指定父权限下的所有子权限"""
    try:
        return await service.get_permissions_by_parent_id(parent_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# 注册路由
module_app.include_router(router, prefix="/permissions", tags=["权限管理"])