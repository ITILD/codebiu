"""
系统默认管理员账户配置

在 config.dev.yaml 的 admin 段配置默认管理员:
    admin:
      username: admin          # 管理员用户名
      password: admin123       # 管理员密码
      nickname: 系统管理员      # 昵称(可选)
      email: admin@xx.com      # 邮箱(可选)
      reset_password: false    # 每次启动将密码重置为配置值(忘记密码时使用)

服务启动时由 BootstrapService 读取本配置,幂等创建/修复管理员账户,
并绑定全局域 "*" 的 admin 角色(拥有全部权限)。
"""
from dataclasses import dataclass

from common.config.index import conf
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
