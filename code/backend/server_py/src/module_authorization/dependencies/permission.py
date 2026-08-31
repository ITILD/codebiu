"""
Casbin 权限校验依赖(全局/模块级)

域(dom)约定:
    dom = 模块名(sys/main/rag/blog...),如项目列表、模块设置等模块级资源

角色体系: 全局仅 admin/user 两个内置角色(见 casbin_rule.py 说明),
用户-角色绑定统一存全局域 "*"(g 表三元组 user/role/"*"),
admin 策略穿透一切,user 策略由各模块 default_policies 合并而来。

项目级权限(如 rag 模块的项目内资源)不走本模块,
由业务模块基于成员表固定档位自行校验(如 module_rag/dependencies/permission.py)。

用法示例:
    # 模块级校验(创建知识库项目需要 rag 域 project 资源的 create 权限)
    @router.post("", dependencies=[Depends(require_permission("rag", "project", "create"))])

    # 服务层手动校验
    await enforce_permission(user_id, "rag", "doc", "upload")
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
    :param dom: 域(模块名)
    :param obj: 资源对象
    :param act: 动作
    :return: 是否有权限
    """
    if auth_manager.enforcer is None:
        logger.warning("Casbin enforcer 未初始化,拒绝所有请求")
        return False
    try:
        # 注: AsyncEnforcer 的 enforce 是同步方法(返回bool),不能 await
        return auth_manager.enforcer.enforce(user_id, dom, obj, act)
    except Exception as e:
        logger.error(f"权限检查异常: {e}")
        return False


async def enforce_permission(user_id: str, dom: str, obj: str, act: str) -> None:
    """
    权限检查(无权限时抛出403)
    :param user_id: 用户ID
    :param dom: 域(模块名)
    :param obj: 资源对象
    :param act: 动作
    """
    if not await check_permission(user_id, dom, obj, act):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"无操作权限: {dom}/{obj}/{act}",
        )


def require_permission(module: str, obj: str, act: str):
    """
    模块级权限校验依赖工厂
    :param module: 模块域(sys/main/rag/blog)
    :param obj: 资源对象
    :param act: 动作
    """
    async def dependency(
        current_user_id: str = Depends(get_current_user_id),
    ) -> str:
        await enforce_permission(current_user_id, module, obj, act)
        return current_user_id

    return dependency


async def sync_default_user_roles(user_id: str, is_first_user: bool = False) -> None:
    """
    为新用户分配内置角色
    :param user_id: 用户ID
    :param is_first_user: 是否为系统首个用户(首个用户自动引导为全局管理员,
                          否则全新系统将无人拥有权限管理能力)
    """
    if auth_manager.enforcer is None:
        logger.warning("Casbin enforcer 未初始化,跳过默认角色分配")
        return
    enforcer = auth_manager.enforcer
    try:
        # 首个注册用户引导为全局管理员(全局域 "*" 的 admin 角色)
        if is_first_user:
            # 注: has_grouping_policy 是同步方法(返回bool),不能 await
            if not enforcer.has_grouping_policy(user_id, "admin", "*"):
                await enforcer.add_grouping_policy(user_id, "admin", "*")
            logger.info(f"首个用户 {user_id} 已引导为全局管理员")
        # 其余用户绑定内置 user 角色(策略为各模块声明的新用户默认权限)
        if not enforcer.has_grouping_policy(user_id, "user", "*"):
            await enforcer.add_grouping_policy(user_id, "user", "*")
    except Exception as e:
        logger.error(f"分配默认角色失败: {e}")


async def get_permission_service() -> PermissionService:
    """权限Service工厂(供 controller 依赖注入)"""
    return PermissionService(PermissionDao())
