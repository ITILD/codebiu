"""默认管理员账户引导(动态配置)

管理员引导参数来自配置中心的 admin 组(首次启动由 yaml 种子, 之后以 DB 为准,
可在"系统管理-通用配置"页调整; password 为密钥字段回读打码)。

启动时由 ensure_default_admin 读取本配置,幂等创建/修复管理员账户,
并绑定全局域 "*" 的 admin 角色(拥有全部权限)。
幂等说明: 重复启动安全,已存在且状态一致时不产生任何写操作。
"""
from common.config.dynamic import get_settings
from common.config.dynamic.schemas import AdminSettings
from common.utils.security.password import hash_password, verify_password
from module_authorization.dao.user import UserDao
from module_authorization.do.user import User, UserCreate, UserResponse, UserUpdate
import logging

logger = logging.getLogger(__name__)


async def ensure_default_admin() -> None:
    """幂等创建/修复默认管理员(建表后启动钩子调用, casbin 未初始化时跳过)"""
    # 延迟导入避免循环依赖
    from module_authorization.config.casbin_rule import auth_manager

    if auth_manager.enforcer is None:
        logger.warning("Casbin enforcer 未初始化,跳过默认管理员引导")
        return

    cfg = await get_settings(AdminSettings)
    user_dao = UserDao()
    try:
        user = await user_dao.get_by_username(cfg.username)
        if user is None:
            await _create_admin(user_dao, cfg)
        else:
            await _repair_admin(user_dao, user, cfg)
    except Exception as e:
        logger.error(f"默认管理员引导失败: {e}")


async def _create_admin(user_dao: UserDao, cfg: AdminSettings) -> None:
    """创建默认管理员账户并绑定全局管理员角色"""
    created: UserResponse = await user_dao.add(
        UserCreate(
            username=cfg.username,
            password=hash_password(cfg.password),
            nickname=cfg.nickname,
            email=cfg.email,
            is_active=True,
        )
    )
    await _bind_admin_role(created.id)
    logger.info(f"默认管理员 '{cfg.username}' 已创建并拥有全部权限")


async def _repair_admin(user_dao: UserDao, user: User, cfg: AdminSettings) -> None:
    """
    修复已存在的管理员账户(角色绑定/禁用状态/密码)
    :param user: 数据库中的用户对象
    :param cfg: 当前动态管理员配置
    """
    # 修复全局管理员角色绑定
    await _bind_admin_role(user.id)

    # 收集需要修复的字段
    updates: dict = {}
    if not user.is_active:
        updates["is_active"] = True
    if cfg.reset_password and not verify_password(cfg.password, user.password):
        updates["password"] = hash_password(cfg.password)

    if updates:
        await user_dao.update(user.id, UserUpdate(**updates))
        logger.info(
            f"默认管理员 '{cfg.username}' 已修复: {list(updates.keys())}"
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
