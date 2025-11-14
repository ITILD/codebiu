from module_authorization.dao.casbin_rule import CasbinRuleDao
from module_authorization.config.casbin_config import enforcer


class CasbinRuleService:
    """Casbin服务类，处理RBAC权限相关的业务逻辑"""

    def __init__(self, dao: CasbinRuleDao):
        """初始化CasbinService
        """
        self.dao = dao
    def add_policy(self, sub: str, obj: str, act: str) -> bool:
        """添加策略规则

        Args:
            sub: 主体（用户或角色）
            obj: 对象（资源）
            act: 动作（操作）

        Returns:
            是否添加成功
        """
        try:
            # 检查规则是否已存在
            if enforcer.has_policy(sub, obj, act):
                return False
            
            # 优先使用enforcer的功能，自动同步到数据库
            return enforcer.add_policy(sub, obj, act)
        except Exception as e:
            print(f"添加策略失败: {e}")
            return False

    def remove_policy(self, sub: str, obj: str, act: str) -> bool:
        """删除策略规则

        Args:
            sub: 主体（用户或角色）
            obj: 对象（资源）
            act: 动作（操作）

        Returns:
            是否删除成功
        """
        try:
            # 优先使用enforcer的功能，自动同步到数据库
            return enforcer.remove_policy(sub, obj, act)
        except Exception as e:
            print(f"删除策略失败: {e}")
            return False

    def add_role_for_user(self, user_id: str, role_key: str) -> bool:
        """为用户添加角色

        Args:
            user_id: 用户ID
            role_key: 角色键

        Returns:
            是否添加成功
        """
        try:
            # 检查是否已存在
            if enforcer.has_grouping_policy(user_id, role_key):
                return False
            
            # 优先使用enforcer的功能，自动同步到数据库
            return enforcer.add_grouping_policy(user_id, role_key)
        except Exception as e:
            print(f"添加用户角色失败: {e}")
            return False

    def remove_role_for_user(self, user_id: str, role_key: str) -> bool:
        """删除用户的角色

        Args:
            user_id: 用户ID
            role_key: 角色键

        Returns:
            是否删除成功
        """
        try:
            # 优先使用enforcer的功能，自动同步到数据库
            return enforcer.remove_grouping_policy(user_id, role_key)
        except Exception as e:
            print(f"删除用户角色失败: {e}")
            return False

    def get_roles_for_user(self, user_id: str) -> list[str]:
        """获取用户的所有角色

        Args:
            user_id: 用户ID

        Returns:
            角色列表
        """
        return enforcer.get_roles_for_user(user_id)

    def get_permissions_for_role(self, role_key: str) -> list[tuple[str, str, str]]:
        """获取角色的所有权限

        Args:
            role_key: 角色键

        Returns:
            权限列表，每项为(sub, obj, act)元组
        """
        permissions = enforcer.get_filtered_policy(0, role_key)
         # 转换格式
        formatted_permissions = [
            {
                "permission_code": perm[1],
                "method": perm[2]
            }
            for perm in permissions
        ]
        return formatted_permissions

    def has_permission(self, user_id: str, obj: str, act: str) -> bool:
        """检查用户是否有指定权限

        Args:
            user_id: 用户ID
            obj: 对象（资源）
            act: 动作（操作）

        Returns:
            是否有权限
        """
        try:
            return enforcer.enforce(user_id, obj, act)
        except Exception as e:
            print(f"权限检查失败: {e}")
            # 在发生错误时默认拒绝访问
            return False

    def batch_add_role_permissions(self, role_key: str, permissions: list[tuple[str, str]]) -> int:
        """批量添加角色权限

        Args:
            role_key: 角色键
            permissions: 权限列表，每项为(permission_code, method)元组

        Returns:
            添加成功的权限数量
        """
        added_count = 0
        
        try:
            # 先删除角色的所有现有权限
            enforcer.remove_filtered_policy(0, role_key)
            
            # 批量添加新权限
            for permission_code, method in permissions:
                # 优先使用enforcer的功能，自动同步到数据库
                if enforcer.add_policy(role_key, permission_code, method):
                    added_count += 1
        except Exception as e:
            print(f"批量添加角色权限失败: {e}")
            
        return added_count

    def batch_add_user_roles(self, user_id: str, role_keys: list[str]) -> int:
        """批量添加用户角色

        Args:
            user_id: 用户ID
            role_keys: 角色键列表

        Returns:
            添加成功的角色数量
        """
        added_count = 0
        
        try:
            # 先删除用户的所有现有角色
            enforcer.remove_filtered_grouping_policy(0, user_id)
            
            # 批量添加新角色
            for role_key in role_keys:
                # 优先使用enforcer的功能，自动同步到数据库
                if enforcer.add_grouping_policy(user_id, role_key):
                    added_count += 1
        except Exception as e:
            print(f"批量添加用户角色失败: {e}")
            
        return added_count

    def delete_role_permissions(self, role_key: str) -> int:
        """删除角色的所有权限

        Args:
            role_key: 角色键

        Returns:
            删除的权限数量
        """
        try:
            # 优先使用enforcer的功能，自动同步到数据库
            policy_count = len(enforcer.get_filtered_policy(0, role_key))
            enforcer.remove_filtered_policy(0, role_key)
            return policy_count
        except Exception as e:
            print(f"删除角色权限失败: {e}")
            return 0

    def delete_user_roles(self, user_id: str) -> int:
        """删除用户的所有角色

        Args:
            user_id: 用户ID

        Returns:
            删除的角色数量
        """
        try:
            # 优先使用enforcer的功能，自动同步到数据库
            role_count = len(enforcer.get_roles_for_user(user_id))
            enforcer.remove_filtered_grouping_policy(0, user_id)
            return role_count
        except Exception as e:
            print(f"删除用户角色失败: {e}")
            return 0

    def reload_policy(self) -> None:
        """重新从数据库加载策略
        """
        try:
            # 优先使用enforcer的内置方法
            enforcer.load_policy()
        except Exception as e:
            print(f"重新加载策略失败: {e}")

    def get_all_policies(self) -> list[tuple[str, str, str]]:
        """获取所有策略规则

        Returns:
            策略规则列表
        """
        try:
            return enforcer.get_policy()
        except Exception as e:
            print(f"获取所有策略失败: {e}")
            return []

    def get_all_grouping_policies(self) -> list[tuple[str, str]]:
        """获取所有角色分配规则

        Returns:
            角色分配规则列表
        """
        try:
            return enforcer.get_grouping_policy()
        except Exception as e:
            print(f"获取所有角色分配规则失败: {e}")
            return []