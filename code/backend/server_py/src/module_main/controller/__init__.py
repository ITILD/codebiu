# 触发模块配置加载(注册建表后启动钩子: 基础字典引导)
from module_main.config import server  # noqa: F401

__all__ = [
    "static",
    "status",
    "db"
]
