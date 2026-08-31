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
            # 注: has_grouping_policy 是同步方法(返回bool),不能 await
            if self.enforcer.has_grouping_policy(user_id, role_key, dom):
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
            # 注: get_filtered_policy 是同步方法(返回list),不能 await
            permissions = self.enforcer.get_filtered_policy(0, role_key)
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
            # 注: enforce 是同步方法(返回bool),不能 await
            return self.enforcer.enforce(user_id, dom, obj, act)
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
            # 注: get_filtered_policy 是同步方法(返回list),不能 await
            policy_count = len(self.enforcer.get_filtered_policy(0, role_key, dom))
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
            # 注: AsyncEnforcer 的 get_policy 是同步方法(返回list),不能 await
            return self.enforcer.get_policy()
        except Exception as e:
            logger.error(f"获取所有策略失败: {e}")
            return []

    async def get_all_grouping_policies(self) -> list[tuple[str, str]]:
        """获取所有角色分配规则

        Returns:
            角色分配规则列表
        """
        try:
            # 注: AsyncEnforcer 的 get_grouping_policy 是同步方法(返回list),不能 await
            return self.enforcer.get_grouping_policy()
        except Exception as e:
            logger.error(f"获取所有角色分配规则失败: {e}")
            return []

    async def get_role_node_codes(self, role_key: str) -> list[str]:
        """
        获取角色当前拥有的节点级权限码列表(角色授权界面勾选回显)

        只返回角色策略与权限树按钮节点的交集对应的权限码,
        模块预设的通配策略(如 rag:* 资源)不参与回显

        Args:
            role_key: 角色键

        Returns:
            按钮级权限码列表,如 ["rag:project:create", "sys:user:read"]
        """
        from module_authorization.config.registry import permission_registry

        try:
            node_set = set(permission_registry.iter_node_policies())
            current = self.enforcer.get_filtered_policy(0, role_key)
            existing = {(p[1], p[2], p[3]) for p in current}
            return [":".join(key) for key in existing & node_set]
        except Exception as e:
            logger.error(f"获取角色节点权限码失败: {e}")
            return []

    async def sync_role_node_policies(self, role_key: str, codes: list[str]) -> dict:
        """
        全量同步角色的节点级权限(角色授权界面勾选提交)
        仅处理权限树按钮节点对应的策略,模块预设的通配策略(如 rag:* 资源)不受影响

        Args:
            role_key: 角色键
            codes: 勾选的权限码列表(按钮级 "模块:资源:动作" 自动解析为策略)

        Returns:
            {"removed": 收回数量, "added": 新授数量}
        """
        from module_authorization.config.registry import (
            permission_registry,
            parse_perm_code,
        )

        try:
            # 解析勾选的权限码 → (dom, obj, act) 集合(忽略目录/菜单级权限码)
            selected: set[tuple[str, str, str]] = set()
            for code in codes:
                parsed = parse_perm_code(code)
                if parsed:
                    selected.add(parsed)

            # 全部模块声明的节点级策略集合(可分配权限的边界)
            node_set: set[tuple[str, str, str]] = set(
                permission_registry.iter_node_policies()
            )

            # 该角色当前全部策略中属于节点级的部分
            current = self.enforcer.get_filtered_policy(0, role_key)
            existing: set[tuple[str, str, str]] = {
                (p[1], p[2], p[3]) for p in current
            }

            removed = 0
            added = 0
            # 收回: 已拥有节点权限但未勾选
            for key in existing & node_set:
                if key not in selected:
                    await self.enforcer.remove_policy(role_key, *key)
                    removed += 1
            # 授予: 勾选但尚未拥有
            for key in selected - existing:
                await self.enforcer.add_policy(role_key, *key)
                added += 1
            return {"removed": removed, "added": added}
        except Exception as e:
            logger.error(f"同步角色节点权限失败: {e}")
            return {"removed": 0, "added": 0}
