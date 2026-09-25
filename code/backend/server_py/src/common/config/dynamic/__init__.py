"""动态配置中心出口: 业务代码统一 `from common.config.dynamic import get_settings`

组注册与更新钩子在此集中完成; 消费方也可直接从 schemas 导入具名 Settings 类。
"""
from typing import TypeVar

from common.config.dynamic.schemas import GROUPS
from common.config.dynamic.schemas import (
    AdminSettings,  # noqa: F401
    DBCacheSettings,  # noqa: F401
    DBGraphSettings,  # noqa: F401
    DBVectorSettings,  # noqa: F401
    EmailSettings,  # noqa: F401
    FileSystemSettings,  # noqa: F401
    TasksSettings,  # noqa: F401
    TokenSettings,  # noqa: F401
    WebSearchSettings,  # noqa: F401
)
from common.config.dynamic.service import settings_service

T = TypeVar("T")

for _schema in GROUPS:
    settings_service.register(_schema)


async def get_settings(schema: type[T]) -> T:
    """类型化读取配置组(业务代码唯一入口)"""
    return await settings_service.get(schema)


async def seed_from_yaml(conf) -> None:
    """首启种子(init_runtime 装配时调用; 幂等, 不覆盖已有行)"""
    await settings_service.seed_from_yaml(conf)


# tasks 组更新钩子: 配置变更后使 celery app 缓存失效(下次访问按新参数重建)
from common.config.tasks import invalidate_celery_app

settings_service.on_update("tasks", invalidate_celery_app)
