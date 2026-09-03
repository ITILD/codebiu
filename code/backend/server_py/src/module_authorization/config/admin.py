"""
系统默认管理员账户配置与启动引导

在 config.dev.yaml 的 admin 段配置默认管理员:
    admin:
      username: admin          # 管理员用户名
      password: admin123       # 管理员密码
      nickname: 系统管理员      # 昵称(可选)
      email: admin@xx.com      # 邮箱(可选)
      reset_password: false    # 每次启动将密码重置为配置值(忘记密码时使用)

启动时由 ensure_default_admin 读取本配置,幂等创建/修复管理员账户,
并绑定全局域 "*" 的 admin 角色(拥有全部权限)。
幂等说明: 重复启动安全,已存在且状态一致时不产生任何写操作。
"""
from dataclasses import dataclass

from common.config.index import conf
from common.utils.security.password import hash_password, verify_password
from module_authorization.dao.user import UserDao
from module_authorization.do.user import User, UserCreate, UserResponse, UserUpdate
import logging

logger = logging.getLogger(__name__)


@dataclass
class AdminConfig:
    """系统默认管理员配置"""

    username: str = "admin"  # 管理员用户名
    password: str = "admin123"  # 管理员密码
    nickname: str | None = None  # 昵称
    email: str | None = None  # 邮箱
    # 每次启动将密码重置为配置值(忘记密码时改为 true 重启恢复)
    reset_password: bool = False


def _load_admin_config() -> AdminConfig | None:
    """
    从配置文件读取管理员配置
    :return: AdminConfig 配置对象;未配置 admin 段时返回 None
    """
    if "admin" not in conf or not conf.admin:
        return None
    try:
        section = conf.admin
        return AdminConfig(
            username=section.get("username", "admin"),
            password=section.get("password", "admin123"),
            nickname=section.get("nickname"),
            email=section.get("email"),
            reset_password=section.get("reset_password", False),
        )
    except Exception as e:
        logger.error(f"读取管理员配置失败: {e}")
        return None


# 全局管理员配置单例(未配置时为 None,启动引导将跳过)
admin_config: AdminConfig | None = _load_admin_config()
if admin_config is None:
    logger.warning("未配置 admin 段,跳过系统默认管理员引导")


async def ensure_default_admin() -> None:
    """幂等创建/修复默认管理员(建表后启动钩子调用,未配置或 casbin 未初始化时跳过)"""
    if admin_config is None:
        return
    # 延迟导入避免循环依赖
    from module_authorization.config.casbin_rule import auth_manager

    if auth_manager.enforcer is None:
        logger.warning("Casbin enforcer 未初始化,跳过默认管理员引导")
        return

    user_dao = UserDao()
    try:
        user = await user_dao.get_by_username(admin_config.username)
        if user is None:
            await _create_admin(user_dao)
        else:
            await _repair_admin(user_dao, user)
    except Exception as e:
        logger.error(f"默认管理员引导失败: {e}")


async def _create_admin(user_dao: UserDao) -> None:
    """创建默认管理员账户并绑定全局管理员角色"""
    created: UserResponse = await user_dao.add(
        UserCreate(
            username=admin_config.username,
            password=hash_password(admin_config.password),
            nickname=admin_config.nickname,
            email=admin_config.email,
            is_active=True,
        )
    )
    await _bind_admin_role(created.id)
    logger.info(f"默认管理员 '{admin_config.username}' 已创建并拥有全部权限")


async def _repair_admin(user_dao: UserDao, user: User) -> None:
    """
    修复已存在的管理员账户(角色绑定/禁用状态/密码)
    :param user: 数据库中的用户对象
    """
    # 修复全局管理员角色绑定
    await _bind_admin_role(user.id)

    # 收集需要修复的字段
    updates: dict = {}
    if not user.is_active:
        updates["is_active"] = True
    if admin_config.reset_password and not verify_password(
        admin_config.password, user.password
    ):
        updates["password"] = hash_password(admin_config.password)

    if updates:
        await user_dao.update(user.id, UserUpdate(**updates))
        logger.info(
            f"默认管理员 '{admin_config.username}' 已修复: {list(updates.keys())}"
        )


async def _bind_admin_role(user_id: str) -> None:
    """
    绑定全局域 "*" 的 admin 角色(幂等)
    :param user_id: 用户ID
    """
    from module_authorization.config.casbin_rule import auth_manager

    enforcer = auth_manager.enforcer
    # 注: AsyncEnforcer 的 has_grouping_policy 是同步方法(返回bool),不能 await
    if not enforcer.has_grouping_policy(user_id, "admin", "*"):
        await enforcer.add_grouping_policy(user_id, "admin", "*")
