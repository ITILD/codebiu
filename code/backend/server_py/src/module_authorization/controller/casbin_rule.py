from fastapi import APIRouter, Depends, HTTPException, status
from module_authorization.do.casbin_rule import (
    PolicyRequest,
    RoleForUserRequest,
    BatchAddRolePermissionsRequest,
    BatchAddUserRolesRequest,
    CheckPermissionRequest,
    PermissionCheckResponse,
)
from module_authorization.service.casbin_rule import CasbinRuleService
from module_authorization.dependencies.casbin_rule import get_casbin_rule_service
from module_authorization.config.server import module_app

router = APIRouter()
# 创建API路由器


# API端点
@router.post("/policy", status_code=status.HTTP_201_CREATED)
async def add_policy(
    request: PolicyRequest,
    casbin_service: CasbinRuleService = Depends(get_casbin_rule_service),
):
    """添加策略规则

    Args:
        request: 添加策略请求数据
        casbin_service: Casbin服务实例

    Returns:
        成功添加的策略信息
    """
    success = casbin_service.add_policy(
        sub=request.sub, obj=request.obj, act=request.act
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="策略规则已存在"
        )

    return {"message": "策略规则添加成功", "data": request.dict()}


@router.delete("/policy", status_code=status.HTTP_200_OK)
async def remove_policy(
    request: PolicyRequest,
    casbin_service: CasbinRuleService = Depends(get_casbin_rule_service),
):
    """删除策略规则

    Args:
        request: 删除策略请求数据
        casbin_service: Casbin服务实例

    Returns:
        删除结果信息
    """
    success = casbin_service.remove_policy(
        sub=request.sub, obj=request.obj, act=request.act
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="策略规则不存在"
        )

    return {"message": "策略规则删除成功"}


@router.post("/role-user", status_code=status.HTTP_201_CREATED)
async def add_role_for_user(
    request: RoleForUserRequest,
    casbin_service: CasbinRuleService = Depends(get_casbin_rule_service),
):
    """为用户添加角色

    Args:
        request: 添加角色请求数据
        casbin_service: Casbin服务实例

    Returns:
        添加结果信息
    """
    success = casbin_service.add_role_for_user(
        user_id=request.user_id, role_key=request.role_key
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="用户已拥有该角色"
        )

    return {"message": "角色添加成功"}


@router.delete("/role-user", status_code=status.HTTP_200_OK)
async def remove_role_for_user(
    request: RoleForUserRequest,
    casbin_service: CasbinRuleService = Depends(get_casbin_rule_service),
):
    """删除用户的角色

    Args:
        request: 删除角色请求数据
        casbin_service: Casbin服务实例

    Returns:
        删除结果信息
    """
    success = casbin_service.remove_role_for_user(
        user_id=request.user_id, role_key=request.role_key
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="用户未拥有该角色"
        )

    return {"message": "角色删除成功"}


@router.get("/roles/{user_id}", status_code=status.HTTP_200_OK)
async def get_roles_for_user(
    user_id: str, casbin_service: CasbinRuleService = Depends(get_casbin_rule_service)
):
    """获取用户的所有角色

    Args:
        user_id: 用户ID
        casbin_service: Casbin服务实例

    Returns:
        用户角色列表
    """
    roles = casbin_service.get_roles_for_user(user_id)
    return {"message": "获取成功", "data": roles}


@router.get("/permissions/{role_key}", status_code=status.HTTP_200_OK)
async def get_permissions_for_role(
    role_key: str, casbin_service: CasbinRuleService = Depends(get_casbin_rule_service)
):
    """获取角色的所有权限

    Args:
        role_key: 角色键
        casbin_service: Casbin服务实例

    Returns:
        角色权限列表
    """
    formatted_permissions = casbin_service.get_permissions_for_role(role_key)

    return {"message": "获取成功", "data": formatted_permissions}


@router.post("/check-permission", status_code=status.HTTP_200_OK)
async def check_permission(
    request: CheckPermissionRequest,  # 使用字典接收动态参数
    casbin_service: CasbinRuleService = Depends(get_casbin_rule_service),
):
    """检查用户是否有指定权限

    Args:
        request: 包含user_id, obj, act的请求数据
        casbin_service: Casbin服务实例

    Returns:
        权限检查结果
    """
    # 验证请求参数
    has_permission = casbin_service.has_permission(
        user_id=request.user_id, obj=request.obj, act=request.act
    )
    return PermissionCheckResponse(has_permission=has_permission)


@router.post("/batch-role-permissions", status_code=status.HTTP_201_CREATED)
async def batch_add_role_permissions(
    request: BatchAddRolePermissionsRequest,
    casbin_service: CasbinRuleService = Depends(get_casbin_rule_service),
):
    """批量添加角色权限

    Args:
        request: 批量添加角色权限请求数据
        casbin_service: Casbin服务实例

    Returns:
        添加结果信息
    """
    # 转换权限格式
    permissions = [
        (perm["permission_code"], perm["method"]) for perm in request.permissions
    ]

    added_count = casbin_service.batch_add_role_permissions(
        role_key=request.role_key, permissions=permissions
    )

    return {"message": f"成功添加{added_count}个权限", "added_count": added_count}


@router.post("/batch-user-roles", status_code=status.HTTP_201_CREATED)
async def batch_add_user_roles(
    request: BatchAddUserRolesRequest,
    casbin_service: CasbinRuleService = Depends(get_casbin_rule_service),
):
    """批量添加用户角色

    Args:
        request: 批量添加用户角色请求数据
        casbin_service: Casbin服务实例

    Returns:
        添加结果信息
    """
    added_count = casbin_service.batch_add_user_roles(
        user_id=request.user_id, role_keys=request.role_keys
    )

    return {"message": f"成功添加{added_count}个角色", "added_count": added_count}


@router.delete("/role-permissions/{role_key}", status_code=status.HTTP_200_OK)
async def delete_role_permissions(
    role_key: str, casbin_service: CasbinRuleService = Depends(get_casbin_rule_service)
):
    """删除角色的所有权限

    Args:
        role_key: 角色键
        casbin_service: CasbinService实例

    Returns:
        删除结果信息
    """
    deleted_count = casbin_service.delete_role_permissions(role_key)

    return {"message": f"成功删除{deleted_count}个权限", "deleted_count": deleted_count}


@router.delete("/user-roles/{user_id}", status_code=status.HTTP_200_OK)
async def delete_user_roles(
    user_id: str, casbin_service: CasbinRuleService = Depends(get_casbin_rule_service)
):
    """删除用户的所有角色

    Args:
        user_id: 用户ID
        casbin_service: CasbinService实例

    Returns:
        删除结果信息
    """
    deleted_count = casbin_service.delete_user_roles(user_id)

    return {"message": f"成功删除{deleted_count}个角色", "deleted_count": deleted_count}


@router.post("/reload-policy", status_code=status.HTTP_200_OK)
async def reload_policy(
    casbin_service: CasbinRuleService = Depends(get_casbin_rule_service),
):
    """重新加载策略规则

    Args:
        casbin_service: CasbinService实例

    Returns:
        重新加载结果信息
    """
    casbin_service.reload_policy()

    return {"message": "策略规则重新加载成功"}


# 注册路由
module_app.include_router(router, prefix="/casbin_rules", tags=["权限规则管理"])
