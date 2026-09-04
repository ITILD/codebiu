from fastapi import APIRouter, Depends, HTTPException, status
from module_authorization.do.casbin_rule import (
    PolicyRequest,
    RoleForUserRequest,
    BatchAddRolePermissionsRequest,
    BatchAddUserRolesRequest,
    CheckPermissionRequest,
    PermissionCheckResponse,
    RolePermsSyncRequest,
)
from module_authorization.service.casbin_rule import CasbinRuleService
from module_authorization.dependencies.casbin_rule import get_casbin_rule_service
from module_authorization.dependencies.permission import require_permission
from module_authorization.config.registry import permission_registry
from module_authorization.config.server import module_app

router = APIRouter()
# 创建API路由器


# API端点
@router.post(
    "/policy",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("sys", "casbin", "create"))],
)
async def add_policy(
    request: PolicyRequest,
    casbin_service: CasbinRuleService = Depends(get_casbin_rule_service),
):
    """添加策略规则

    Args:
        request: 添加策略请求数据（包含sub, dom, obj, act）
        casbin_service: Casbin服务实例

    Returns:
        成功添加的策略信息
    """
    success = await casbin_service.add_policy(
        sub=request.sub, dom=request.dom, obj=request.obj, act=request.act
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="策略规则已存在"
        )

    return {"message": "策略规则添加成功", "data": request.dict()}


@router.delete(
    "/policy",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("sys", "casbin", "delete"))],
)
async def remove_policy(
    request: PolicyRequest,
    casbin_service: CasbinRuleService = Depends(get_casbin_rule_service),
):
    """删除策略规则

    Args:
        request: 删除策略请求数据（包含sub, dom, obj, act）
        casbin_service: Casbin服务实例

    Returns:
        删除结果信息
    """
    success = await casbin_service.remove_policy(
        sub=request.sub, dom=request.dom, obj=request.obj, act=request.act
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="策略规则不存在"
        )

    return {"message": "策略规则删除成功"}


@router.post(
    "/role-user",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("sys", "casbin", "create"))],
)
async def add_role_for_user(
    request: RoleForUserRequest,
    casbin_service: CasbinRuleService = Depends(get_casbin_rule_service),
):
    """为用户添加角色

    Args:
        request: 添加角色请求数据（包含user_id, role_key, dom）
        casbin_service: Casbin服务实例

    Returns:
        添加结果信息
    """
    success = await casbin_service.add_role_for_user(
        user_id=request.user_id, role_key=request.role_key, dom=request.dom
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="用户已拥有该角色"
        )

    return {"message": "角色添加成功"}


@router.delete(
    "/role-user",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("sys", "casbin", "delete"))],
)
async def remove_role_for_user(
    request: RoleForUserRequest,
    casbin_service: CasbinRuleService = Depends(get_casbin_rule_service),
):
    """删除用户的角色

    Args:
        request: 删除角色请求数据（包含user_id, role_key, dom）
        casbin_service: Casbin服务实例

    Returns:
        删除结果信息
    """
    success = await casbin_service.remove_role_for_user(
        user_id=request.user_id, role_key=request.role_key, dom=request.dom
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="用户未拥有该角色"
        )

    return {"message": "角色删除成功"}


@router.get(
    "/roles/{user_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("sys", "casbin", "read"))],
)
async def get_roles_for_user(
    user_id: str, dom: str = "*", casbin_service: CasbinRuleService = Depends(get_casbin_rule_service)
):
    """获取用户的所有角色

    Args:
        user_id: 用户ID
        dom: 域(项目ID或"*"表示全局，默认为全局)
        casbin_service: Casbin服务实例

    Returns:
        用户角色列表
    """
    roles = await casbin_service.get_roles_for_user(user_id, dom)
    return {"message": "获取成功", "data": roles}


@router.get(
    "/permissions/{role_key}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("sys", "casbin", "read"))],
)
async def get_permissions_for_role(
    role_key: str, dom: str = "*", casbin_service: CasbinRuleService = Depends(get_casbin_rule_service)
):
    """获取角色的所有权限

    Args:
        role_key: 角色键
        dom: 域(项目ID或"*"表示全局，默认为全局)
        casbin_service: Casbin服务实例

    Returns:
        角色权限列表
    """
    formatted_permissions = await casbin_service.get_permissions_for_role(role_key, dom)

    return {"message": "获取成功", "data": formatted_permissions}


@router.post(
    "/check-permission",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("sys", "casbin", "read"))],
)
async def check_permission(
    request: CheckPermissionRequest,
    casbin_service: CasbinRuleService = Depends(get_casbin_rule_service),
):
    """检查用户是否有指定权限

    Args:
        request: 包含user_id, dom, obj, act的请求数据
        casbin_service: Casbin服务实例

    Returns:
        权限检查结果
    """
    has_permission = await casbin_service.has_permission(
        user_id=request.user_id, dom=request.dom, obj=request.obj, act=request.act
    )
    return PermissionCheckResponse(has_permission=has_permission)


@router.post(
    "/batch-role-permissions",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("sys", "casbin", "create"))],
)
async def batch_add_role_permissions(
    request: BatchAddRolePermissionsRequest,
    casbin_service: CasbinRuleService = Depends(get_casbin_rule_service),
):
    """批量添加角色权限

    Args:
        request: 批量添加角色权限请求数据（包含role_key, dom, permissions）
        casbin_service: Casbin服务实例

    Returns:
        添加结果信息
    """
    # 转换权限格式
    permissions = [
        (perm["permission_code"], perm["method"]) for perm in request.permissions
    ]

    added_count = await casbin_service.batch_add_role_permissions(
        role_key=request.role_key, dom=request.dom, permissions=permissions
    )

    return {"message": f"成功添加{added_count}个权限", "added_count": added_count}


@router.post(
    "/batch-user-roles",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("sys", "casbin", "create"))],
)
async def batch_add_user_roles(
    request: BatchAddUserRolesRequest,
    casbin_service: CasbinRuleService = Depends(get_casbin_rule_service),
):
    """批量添加用户角色

    Args:
        request: 批量添加用户角色请求数据（包含user_id, role_keys, dom）
        casbin_service: Casbin服务实例

    Returns:
        添加结果信息
    """
    added_count = await casbin_service.batch_add_user_roles(
        user_id=request.user_id, dom=request.dom, role_keys=request.role_keys
    )

    return {"message": f"成功添加{added_count}个角色", "added_count": added_count}


@router.delete(
    "/role-permissions/{role_key}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("sys", "casbin", "delete"))],
)
async def delete_role_permissions(
    role_key: str, dom: str = "*", casbin_service: CasbinRuleService = Depends(get_casbin_rule_service)
):
    """删除角色的所有权限

    Args:
        role_key: 角色键
        dom: 域(项目ID或"*"表示全局，默认为全局)
        casbin_service: CasbinService实例

    Returns:
        删除结果信息
    """
    deleted_count = await casbin_service.delete_role_permissions(role_key, dom)

    return {"message": f"成功删除{deleted_count}个权限", "deleted_count": deleted_count}


@router.delete(
    "/user-roles/{user_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("sys", "casbin", "delete"))],
)
async def delete_user_roles(
    user_id: str, dom: str = "*", casbin_service: CasbinRuleService = Depends(get_casbin_rule_service)
):
    """删除用户的所有角色

    Args:
        user_id: 用户ID
        dom: 域(项目ID或"*"表示全局，默认为全局)
        casbin_service: CasbinService实例

    Returns:
        删除结果信息
    """
    deleted_count = await casbin_service.delete_user_roles(user_id, dom)

    return {"message": f"成功删除{deleted_count}个角色", "deleted_count": deleted_count}


@router.post(
    "/reload-policy",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("sys", "casbin", "update"))],
)
async def reload_policy(
    casbin_service: CasbinRuleService = Depends(get_casbin_rule_service),
):
    """重新加载策略规则

    Args:
        casbin_service: CasbinService实例

    Returns:
        重新加载结果信息
    """
    await casbin_service.reload_policy()

    return {"message": "策略规则重新加载成功"}


@router.get(
    "/policies",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("sys", "casbin", "read"))],
)
async def get_all_policies(
    dom: str | None = None,
    casbin_service: CasbinRuleService = Depends(get_casbin_rule_service),
):
    """获取全部策略规则(可按域过滤)

    Args:
        dom: 域过滤(为空返回全部)
        casbin_service: Casbin服务实例

    Returns:
        策略规则列表 [sub, dom, obj, act]
    """
    policies = await casbin_service.get_all_policies()
    if dom:
        policies = [p for p in policies if p[1] == dom or p[1] == "*"]
    return {"message": "获取成功", "data": [list(p) for p in policies]}


@router.get(
    "/grouping-policies",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("sys", "casbin", "read"))],
)
async def get_all_grouping_policies(
    dom: str | None = None,
    casbin_service: CasbinRuleService = Depends(get_casbin_rule_service),
):
    """获取全部用户-角色绑定规则(可按域过滤)

    Args:
        dom: 域过滤(为空返回全部)
        casbin_service: Casbin服务实例

    Returns:
        角色绑定规则列表 [user_id, role_key, dom]
    """
    policies = await casbin_service.get_all_grouping_policies()
    if dom:
        policies = [p for p in policies if p[2] == dom or p[2] == "*"]
    return {"message": "获取成功", "data": [list(p) for p in policies]}


# ---------------- 模块声明树与角色授权(声明驱动) ----------------

def _node_to_dict(node) -> dict:
    """将声明节点转换为前端树结构"""
    return {
        "name": node.name,
        "code": node.code,
        "menu_type": node.menu_type,
        "path": node.path,
        "icon": node.icon,
        "order_num": node.order_num,
        "children": [_node_to_dict(child) for child in node.children],
    }


@router.get(
    "/module-tree",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("sys", "casbin", "read"))],
)
async def get_module_permission_tree():
    """获取全部模块声明的权限树(角色授权界面的可分配权限集合,含各模块根目录)"""
    tree = [
        {
            "name": define.name,
            "code": define.module,
            "menu_type": "M",
            "icon": define.icon,
            "order_num": define.order_num,
            "children": [_node_to_dict(node) for node in define.nodes],
        }
        for define in permission_registry.get_all()
    ]
    return {"message": "获取成功", "data": tree}


@router.get(
    "/role-perms/{role_key}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("sys", "casbin", "read"))],
)
async def get_role_node_codes(
    role_key: str, casbin_service: CasbinRuleService = Depends(get_casbin_rule_service)
):
    """获取角色当前拥有的节点级权限码列表(角色授权界面勾选回显)

    Args:
        role_key: 角色键
        casbin_service: Casbin服务实例

    Returns:
        按钮级权限码列表
    """
    codes = await casbin_service.get_role_node_codes(role_key)
    return {"message": "获取成功", "data": codes}


@router.post(
    "/role-perms",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("sys", "casbin", "update"))],
)
async def sync_role_permissions(
    request: RolePermsSyncRequest,
    casbin_service: CasbinRuleService = Depends(get_casbin_rule_service),
):
    """全量同步角色的节点级权限

    Args:
        request: 角色权限同步请求数据(角色键 + 勾选的权限码列表)
        casbin_service: Casbin服务实例

    Returns:
        同步结果(收回/新增的策略数量)
    """
    result = await casbin_service.sync_role_node_policies(
        role_key=request.role_key, codes=request.codes
    )
    return {
        "message": f"权限同步完成,收回 {result['removed']} 条,新增 {result['added']} 条",
        "data": result,
    }


# 注册路由(须位于全部路由定义之后)
module_app.include_router(router, prefix="/casbin-rules", tags=["权限规则管理"])
