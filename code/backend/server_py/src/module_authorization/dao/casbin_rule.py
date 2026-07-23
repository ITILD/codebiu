from module_authorization.config.casbin_rule import auth_manager
import logging
logger = logging.getLogger(__name__)

class CasbinRuleDao:
    """Casbin规则数据访问对象"""
    def __init__(self):
        self.enforcer = auth_manager.enforcer

    async def add_policy(self, sub: str, dom: str, obj: str, act: str) -> bool:
        """添加策略规则

        Args:
            sub: 主体(用户或角色)
            dom: 域(项目ID或"*"表示全局)
            obj: 对象(资源)
            act: 动作(操作)

        Returns:
            是否添加成功
        """
        try:
            if self.enforcer.has_policy(sub, dom, obj, act):
                return False
            return await self.enforcer.add_policy(sub, dom, obj, act)
        except Exception as e:
            logger.error(f"添加策略失败: {e}")
            return False

    async def remove_policy(self, sub: str, dom: str, obj: str, act: str) -> bool:
        """删除策略规则

        Args:
            sub: 主体(用户或角色)
            dom: 域(项目ID或"*"表示全局)
            obj: 对象(资源)
            act: 动作(操作)

        Returns:
            是否删除成功
        """
        try:
            return await self.enforcer.remove_policy(sub, dom, obj, act)
        except Exception as e:
            logger.error(f"删除策略失败: {e}")
            return False

    async def add_role_for_user(self, user_id: str, role_key: str, dom: str = "*") -> bool:
        """为用户添加角色

        Args:
            user_id: 用户ID
            role_key: 角色键
            dom: 域(项目ID或"*"表示全局，默认为全局)

        Returns:
            是否添加成功
        """
        try:
            if await self.enforcer.has_grouping_policy(user_id, role_key, dom):
                return False
            return await self.enforcer.add_grouping_policy(user_id, role_key, dom)
        except Exception as e:
            logger.error(f"添加用户角色失败: {e}")
            return False

    async def remove_role_for_user(self, user_id: str, role_key: str, dom: str = "*") -> bool:
        """删除用户的角色

        Args:
            user_id: 用户ID
            role_key: 角色键
            dom: 域(项目ID或"*"表示全局，默认为全局)

        Returns:
            是否删除成功
        """
        try:
            return await self.enforcer.remove_grouping_policy(user_id, role_key, dom)
        except Exception as e:
            logger.error(f"删除用户角色失败: {e}")
            return False

    async def get_roles_for_user(self, user_id: str, dom: str = "*") -> list[str]:
        """获取用户的所有角色

        Args:
            user_id: 用户ID
            dom: 域(项目ID或"*"表示全局，默认为全局)

        Returns:
            角色列表
        """
        try:
            return await self.enforcer.get_roles_for_user_in_domain(user_id, dom)
        except Exception as e:
            logger.error(f"获取用户角色失败: {e}")
            return []

    async def get_permissions_for_role(self, role_key: str, dom: str = "*") -> list[dict[str, str]]:
        """获取角色的所有权限

        Args:
            role_key: 角色键
            dom: 域(项目ID或"*"表示全局，默认为全局)

        Returns:
            权限列表，每项为字典包含 domain, permission_code, method
        """
        try:
            permissions = await self.enforcer.get_filtered_policy(0, role_key)
        except Exception as e:
            logger.error(f"获取角色权限失败: {e}")
            return []
        filtered_permissions = [
            perm for perm in permissions if perm[1] == dom or perm[1] == "*"
        ]
        formatted_permissions = [
            {"domain": perm[1], "permission_code": perm[2], "method": perm[3]}
            for perm in filtered_permissions
        ]
        return formatted_permissions

    async def has_permission(self, user_id: str, dom: str, obj: str, act: str) -> bool:
        """检查用户是否有指定权限

        Args:
            user_id: 用户ID
            dom: 域(项目ID或"*"表示全局)
            obj: 对象(资源)
            act: 动作(操作)

        Returns:
            是否有权限
        """
        try:
            return await self.enforcer.enforce(user_id, dom, obj, act)
        except Exception as e:
            logger.error(f"权限检查失败: {e}")
            return False

    async def batch_add_role_permissions(
        self, role_key: str, dom: str, permissions: list[tuple[str, str]]
    ) -> int:
        """批量添加角色权限

        Args:
            role_key: 角色键
            dom: 域(项目ID或"*"表示全局)
            permissions: 权限列表，每项为(permission_code, method)元组

        Returns:
            添加成功的权限数量
        """
        added_count = 0
        try:
            await self.enforcer.remove_filtered_policy(0, role_key, dom)
            for permission_code, method in permissions:
                if await self.enforcer.add_policy(role_key, dom, permission_code, method):
                    added_count += 1
        except Exception as e:
            logger.error(f"批量添加角色权限失败: {e}")
        return added_count

    async def batch_add_user_roles(self, user_id: str, dom: str, role_keys: list[str]) -> int:
        """批量添加用户角色

        Args:
            user_id: 用户ID
            dom: 域(项目ID或"*"表示全局)
            role_keys: 角色键列表

        Returns:
            添加成功的角色数量
        """
        added_count = 0
        try:
            await self.enforcer.remove_filtered_grouping_policy(0, user_id, dom)
            for role_key in role_keys:
                if await self.enforcer.add_grouping_policy(user_id, role_key, dom):
                    added_count += 1
        except Exception as e:
            logger.error(f"批量添加用户角色失败: {e}")
        return added_count

    async def delete_role_permissions(self, role_key: str, dom: str = "*") -> int:
        """删除角色的所有权限

        Args:
            role_key: 角色键
            dom: 域(项目ID或"*"表示全局，默认为全局)

        Returns:
            删除的权限数量
        """
        try:
            policy_count = len(await self.enforcer.get_filtered_policy(0, role_key, dom))
            await self.enforcer.remove_filtered_policy(0, role_key, dom)
            return policy_count
        except Exception as e:
            logger.error(f"删除角色权限失败: {e}")
            return 0

    async def delete_user_roles(self, user_id: str, dom: str = "*") -> int:
        """删除用户的所有角色

        Args:
            user_id: 用户ID
            dom: 域(项目ID或"*"表示全局，默认为全局)

        Returns:
            删除的角色数量
        """
        try:
            role_count = len(await self.enforcer.get_roles_for_user_in_domain(user_id, dom))
            await self.enforcer.remove_filtered_grouping_policy(0, user_id, dom)
            return role_count
        except Exception as e:
            logger.error(f"删除用户角色失败: {e}")
            return 0

    async def reload_policy(self) -> None:
        """重新从数据库加载策略"""
        try:
            await self.enforcer.load_policy()
        except Exception as e:
            logger.error(f"重新加载策略失败: {e}")

    async def get_all_policies(self) -> list[tuple[str, str, str]]:
        """获取所有策略规则

        Returns:
            策略规则列表
        """
        try:
            return await self.enforcer.get_policy()
        except Exception as e:
            logger.error(f"获取所有策略失败: {e}")
            return []

    async def get_all_grouping_policies(self) -> list[tuple[str, str]]:
        """获取所有角色分配规则

        Returns:
            角色分配规则列表
        """
        try:
            return await self.enforcer.get_grouping_policy()
        except Exception as e:
            logger.error(f"获取所有角色分配规则失败: {e}")
            return []
