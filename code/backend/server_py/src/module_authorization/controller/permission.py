from fastapi import APIRouter, status, Depends
from common.utils.fastapiEX.exceptions import NotFoundError
from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_authorization.do.permission import Permission, PermissionCreate, PermissionUpdate, PermissionResponse, PermissionTree
from module_authorization.service.permission import PermissionService
from module_authorization.dependencies.permission import get_permission_service, require_permission
from module_authorization.config.server import module_app

router = APIRouter()

@router.post(
    "", summary="创建权限", status_code=status.HTTP_201_CREATED, response_model=str,
    dependencies=[Depends(require_permission("sys", "permission", "create"))],
)
async def create_permission(
    permission: PermissionCreate,
    service: PermissionService = Depends(get_permission_service)
):
    """创建新权限"""
    return await service.add(permission)

@router.get("/tree", summary="获取权限树形结构", response_model=list[PermissionTree],
    dependencies=[Depends(require_permission("sys", "permission", "read"))])
async def get_permission_tree(
    service: PermissionService = Depends(get_permission_service)
):
    """获取权限/菜单树形结构"""
    return await service.get_tree()

@router.get(
    "/list", summary="分页查询权限列表", response_model=PaginationResponse,
    dependencies=[Depends(require_permission("sys", "permission", "read"))],
)
async def list_permissions(
    pagination: PaginationParams = Depends(),
    service: PermissionService = Depends(get_permission_service)
):
    """按 page/size 分页返回权限列表(本接口无过滤参数,total 为权限总数)
    返回结构 {items, total, page, size, pages};page≥1,size 1~500
    """
    return await service.list_paged(pagination)

@router.get("/{permission_id}", summary="获取单个权限", response_model=Permission,
    dependencies=[Depends(require_permission("sys", "permission", "read"))])
async def get_permission(
    permission_id: str,
    service: PermissionService = Depends(get_permission_service)
):
    """获取单个权限详情, 不存在时返回404"""
    result = await service.get(permission_id)
    if not result:
        raise NotFoundError("权限不存在")
    return result

@router.delete(
    "/{permission_id}", summary="删除权限", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("sys", "permission", "delete"))],
)
async def delete_permission(
    permission_id: str,
    service: PermissionService = Depends(get_permission_service)
):
    """按ID删除权限,权限不存在时报400(dao 层 not-found 抛 ValueError, 由全局处理器映射)
    不做子权限级联校验,成功返回204
    """
    await service.delete(permission_id)

@router.put(
    "/{permission_id}", summary="更新权限", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("sys", "permission", "update"))],
)
async def update_permission(
    permission_id: str,
    permission: PermissionUpdate,
    service: PermissionService = Depends(get_permission_service)
):
    """按ID部分更新权限字段(仅传传入的字段),权限不存在时报400
    更新成功返回204
    """
    await service.update(permission_id, permission)

@router.get("/code/{code}", summary="通过代码获取权限", response_model=Permission,
    dependencies=[Depends(require_permission("sys", "permission", "read"))])
async def get_permission_by_code(
    code: str,
    service: PermissionService = Depends(get_permission_service)
):
    """按权限代码精确匹配查询单个权限,不存在时返回404"""
    result = await service.get_by_code(code)
    if not result:
        raise NotFoundError("权限不存在")
    return result

@router.get("/parent/{parent_id}", summary="获取子权限列表",
    dependencies=[Depends(require_permission("sys", "permission", "read"))])
async def get_permissions_by_parent_id(
    parent_id: str,
    service: PermissionService = Depends(get_permission_service)
):
    """获取指定父权限下的所有子权限"""
    return await service.get_permissions_by_parent_id(parent_id)

# 注册路由
module_app.include_router(router, prefix="/permissions", tags=["权限管理"])