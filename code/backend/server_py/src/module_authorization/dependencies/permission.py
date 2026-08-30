"""
Casbin 权限校验依赖

域(dom)约定:
    模块级资源: dom = 模块名(main/rag),如项目列表、模块设置
    项目级资源: dom = "rag:{project_id}",实现同知识库多用户隔离

用法示例:
    # 模块级校验(创建知识库项目需要 rag 域 project 资源的 create 权限)
    @router.post("", dependencies=[Depends(require_permission("rag", "project", "create"))])

    # 项目级校验(路径含 {project_id} 时自动构造域 rag:{project_id})
    @router.post("/{project_id}/upload", dependencies=[Depends(require_project_permission("doc", "upload"))])

    # 服务层手动校验(已知 project_id 的场景)
    await enforce_project_permission(user_id, project_id, "doc", "delete")
"""
from fastapi import Depends, HTTPException, status
from module_authorization.dependencies.auth import get_current_user_id
from module_authorization.config.casbin_rule import auth_manager
from module_authorization.dao.permission import PermissionDao
from module_authorization.service.permission import PermissionService
import logging

logger = logging.getLogger(__name__)


async def check_permission(user_id: str, dom: str, obj: str, act: str) -> bool:
    """
    底层权限检查(不抛异常)
    :param user_id: 用户ID
    :param dom: 域(模块名或 rag:{project_id})
    :param obj: 资源对象
    :param act: 动作
    :return: 是否有权限
    """
    if auth_manager.enforcer is None:
        logger.warning("Casbin enforcer 未初始化,拒绝所有请求")
        return False
    try:
        return await auth_manager.enforcer.enforce(user_id, dom, obj, act)
    except Exception as e:
        logger.error(f"权限检查异常: {e}")
        return False


async def enforce_permission(user_id: str, dom: str, obj: str, act: str) -> None:
    """
    权限检查(无权限时抛出403)
    """
    if not await check_permission(user_id, dom, obj, act):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"无操作权限: {dom}/{obj}/{act}",
        )


async def enforce_project_permission(
    user_id: str, project_id: str, obj: str, act: str
) -> None:
    """
    项目级权限检查: 域为 rag:{project_id}(同知识库多用户隔离)
    """
    await enforce_permission(user_id, f"rag:{project_id}", obj, act)


def require_permission(module: str, obj: str, act: str):
    """
    模块级权限校验依赖工厂
    :param module: 模块域(main/rag)
    :param obj: 资源对象
    :param act: 动作
    """
    async def dependency(
        current_user_id: str = Depends(get_current_user_id),
    ) -> str:
        await enforce_permission(current_user_id, module, obj, act)
        return current_user_id

    return dependency


def require_project_permission(obj: str, act: str):
    """
    项目级权限校验依赖工厂
    要求路由路径包含 {project_id} 占位符,以域 rag:{project_id} 校验
    :param obj: 资源对象
    :param act: 动作
    """
    async def dependency(
        project_id: str,
        current_user_id: str = Depends(get_current_user_id),
    ) -> str:
        await enforce_project_permission(current_user_id, project_id, obj, act)
        return current_user_id

    return dependency


async def sync_project_member_role(
    user_id: str, project_id: str, role: str, old_role: str | None = None
) -> None:
    """
    同步项目成员角色到 casbin(域 rag:{project_id})
    :param user_id: 用户ID
    :param project_id: 项目ID
    :param role: 新角色
    :param old_role: 旧角色(角色变更时先移除)
    """
    if auth_manager.enforcer is None:
        logger.warning("Casbin enforcer 未初始化,跳过角色同步")
        return
    dom = f"rag:{project_id}"
    try:
        if old_role:
            await auth_manager.enforcer.remove_grouping_policy(user_id, old_role, dom)
        if role:
            if not await auth_manager.enforcer.has_grouping_policy(user_id, role, dom):
                await auth_manager.enforcer.add_grouping_policy(user_id, role, dom)
    except Exception as e:
        logger.error(f"同步项目成员角色失败: {e}")


async def remove_project_roles(project_id: str) -> None:
    """
    清理项目域下的全部角色绑定(项目删除时调用)
    :param project_id: 项目ID
    """
    if auth_manager.enforcer is None:
        return
    dom = f"rag:{project_id}"
    try:
        await auth_manager.enforcer.remove_filtered_grouping_policy(2, dom)
    except Exception as e:
        logger.error(f"清理项目角色失败: {e}")


async def sync_default_user_roles(user_id: str) -> None:
    """
    为新用户分配子模块默认角色(main_viewer/main域 + rag_user/rag域)
    :param user_id: 用户ID
    """
    if auth_manager.enforcer is None:
        logger.warning("Casbin enforcer 未初始化,跳过默认角色分配")
        return
    try:
        for role, dom in (("main_viewer", "main"), ("rag_user", "rag")):
            if not await auth_manager.enforcer.has_grouping_policy(user_id, role, dom):
                await auth_manager.enforcer.add_grouping_policy(user_id, role, dom)
    except Exception as e:
        logger.error(f"分配默认角色失败: {e}")


async def get_permission_service() -> PermissionService:
    """权限Service工厂(供 controller 依赖注入)"""
    return PermissionService(PermissionDao())
