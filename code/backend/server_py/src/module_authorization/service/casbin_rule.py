from module_authorization.dao.casbin_rule import CasbinRuleDao
import casbin
import logging

logger = logging.getLogger(__name__)


class CasbinRuleService:
    """Casbin服务类，处理RBAC权限相关的业务逻辑"""

    def __init__(self, dao: CasbinRuleDao | None = None):
        """初始化CasbinService"""
        self.dao = dao or CasbinRuleDao()

    async def add_policy(self, sub: str, dom: str, obj: str, act: str) -> bool:
        """添加策略规则"""
        return await self.dao.add_policy(sub, dom, obj, act)

    async def remove_policy(self, sub: str, dom: str, obj: str, act: str) -> bool:
        """删除策略规则"""
        return await self.dao.remove_policy(sub, dom, obj, act)

    async def add_role_for_user(
        self, user_id: str, role_key: str, dom: str = "*"
    ) -> bool:
        """为用户添加角色"""
        return await self.dao.add_role_for_user(user_id, role_key, dom)

    async def remove_role_for_user(
        self, user_id: str, role_key: str, dom: str = "*"
    ) -> bool:
        """删除用户的角色"""
        return await self.dao.remove_role_for_user(user_id, role_key, dom)

    async def get_roles_for_user(self, user_id: str, dom: str = "*") -> list[str]:
        """获取用户的所有角色"""
        return await self.dao.get_roles_for_user(user_id, dom)

    async def get_permissions_for_role(
        self, role_key: str, dom: str = "*"
    ) -> list[dict[str, str]]:
        """获取角色的所有权限"""
        return await self.dao.get_permissions_for_role(role_key, dom)

    async def has_permission(self, user_id: str, dom: str, obj: str, act: str) -> bool:
        """检查用户是否有指定权限"""
        return await self.dao.has_permission(user_id, dom, obj, act)

    async def batch_add_role_permissions(
        self, role_key: str, dom: str, permissions: list[tuple[str, str]]
    ) -> int:
        """批量添加角色权限"""
        return await self.dao.batch_add_role_permissions(role_key, dom, permissions)

    async def batch_add_user_roles(
        self, user_id: str, dom: str, role_keys: list[str]
    ) -> int:
        """批量添加用户角色"""
        return await self.dao.batch_add_user_roles(user_id, dom, role_keys)

    async def delete_role_permissions(self, role_key: str, dom: str = "*") -> int:
        """删除角色的所有权限"""
        return await self.dao.delete_role_permissions(role_key, dom)

    async def delete_user_roles(self, user_id: str, dom: str = "*") -> int:
        """删除用户的所有角色"""
        return await self.dao.delete_user_roles(user_id, dom)

    async def reload_policy(self) -> None:
        """重新从数据库加载策略"""
        return await self.dao.reload_policy()

    async def get_all_policies(self) -> list[tuple[str, str, str]]:
        """获取所有策略规则"""
        return await self.dao.get_all_policies()

    async def get_all_grouping_policies(self) -> list[tuple[str, str]]:
        """获取所有角色分配规则"""
        return await self.dao.get_all_grouping_policies()
