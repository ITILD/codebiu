"""
系统默认管理员引导服务

服务启动时根据 config.dev.yaml 的 admin 段幂等创建/修复默认管理员:
    1. 账户不存在 -> 创建账户,并绑定全局域 "*" 的 admin 角色(拥有全部权限)
    2. 账户存在   -> 修复缺失的全局管理员角色绑定;账户被禁用时重新启用;
                    reset_password 为 true 且密码与配置不一致时重置密码

幂等说明: 重复启动安全,已存在且状态一致时不产生任何写操作。
"""
import logging

from common.utils.security.password import hash_password, verify_password
from module_authorization.config.admin import admin_config
from module_authorization.dao.user import UserDao
from module_authorization.do.user import User, UserCreate, UserResponse, UserUpdate

logger = logging.getLogger(__name__)


class BootstrapService:
    """系统默认管理员引导服务"""

    def __init__(self, user_dao: UserDao):
        """
        初始化引导服务
        :param user_dao: 用户DAO对象
        """
        self.user_dao = user_dao

    async def ensure_default_admin(self) -> None:
        """
        幂等确保配置的默认管理员存在且拥有全部权限(启动时调用)
        - 未配置 admin 段或 casbin 未初始化时跳过
        """
        if admin_config is None:
            return
        # 延迟导入避免循环依赖
        from module_authorization.config.casbin_rule import auth_manager

        if auth_manager.enforcer is None:
            logger.warning("Casbin enforcer 未初始化,跳过默认管理员引导")
            return

        try:
            user = await self.user_dao.get_by_username(admin_config.username)
            if user is None:
                await self._create_admin()
            else:
                await self._repair_admin(user)
        except Exception as e:
            logger.error(f"默认管理员引导失败: {e}")

    async def _create_admin(self) -> None:
        """创建默认管理员账户并绑定全局管理员角色"""
        created: UserResponse = await self.user_dao.add(
            UserCreate(
                username=admin_config.username,
                password=hash_password(admin_config.password),
                nickname=admin_config.nickname,
                email=admin_config.email,
                is_active=True,
            )
        )
        await self._bind_admin_role(created.id)
        logger.info(
            f"默认管理员 '{admin_config.username}' 已创建并拥有全部权限"
        )

    async def _repair_admin(self, user: User) -> None:
        """
        修复已存在的管理员账户(角色绑定/禁用状态/密码)
        :param user: 数据库中的用户对象
        """
        # 修复全局管理员角色绑定
        await self._bind_admin_role(user.id)

        # 收集需要修复的字段
        updates: dict = {}
        if not user.is_active:
            updates["is_active"] = True
        if admin_config.reset_password and not verify_password(
            admin_config.password, user.password
        ):
            updates["password"] = hash_password(admin_config.password)

        if updates:
            await self.user_dao.update(user.id, UserUpdate(**updates))
            logger.info(
                f"默认管理员 '{admin_config.username}' 已修复: {list(updates.keys())}"
            )

    async def _bind_admin_role(self, user_id: str) -> None:
        """
        绑定全局域 "*" 的 admin 角色(幂等)
        :param user_id: 用户ID
        """
        from module_authorization.config.casbin_rule import auth_manager

        enforcer = auth_manager.enforcer
        # 注: AsyncEnforcer 的 has_grouping_policy 是同步方法(返回bool),不能 await
        if not enforcer.has_grouping_policy(user_id, "admin", "*"):
            await enforcer.add_grouping_policy(user_id, "admin", "*")
