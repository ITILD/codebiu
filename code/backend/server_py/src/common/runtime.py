"""进程内运行时注册表(唯一的"全局",其余模块级对象均为它的门面代理)

设计原则(Composition Root + Service Locator 门面):
- 启动期装配: init_runtime() 显式完成 连接db_rel(yaml引导) → 建sys_config表 →
  yaml种子 → 刷新任务快照 → 连接其余数据库
- 运行期解析: 业务代码经 common.config.db 的门面代理按"调用时"解析当前实现,
  动态配置刷新/连接重建对存量代码完全透明
- 禁止任何模块在 import 期触发数据库连接(原 db.py import 期 start() 的根因治理)
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class AttrDict(dict):
    """dict 的属性访问适配器(动态配置 model_dump → DBConfigFactory 等属性风格消费者)"""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


class Runtime:
    """运行时对象注册表"""

    def __init__(self) -> None:
        self.db_manager = None   # DatabaseManager(由 common.config.db 装配)
        self.settings = None     # SettingsService(由 common.config.dynamic 装配)
        self.initialized = False


runtime = Runtime()


async def init_runtime() -> None:
    """装配点(幂等): 关系库连接(yaml引导) → sys_config建表 → yaml种子 →
    任务快照刷新 → 其余数据库连接(动态配置)

    由 lifespan.server_start / app_task worker / 需要直连的脚本显式调用。
    """
    if runtime.initialized:
        return
    from common.config.db import manager

    real = manager()
    real.start_rel()                      # 段1: db_rel 来自 yaml(先于动态配置可用)
    runtime.db_manager = real

    await real.create_sys_config_table()  # 段2: 动态配置表先行(种子/读取依赖)

    from common.config.dynamic import seed_from_yaml, settings_service
    runtime.settings = settings_service
    from common.config.index import conf
    await seed_from_yaml(conf)            # 段3: yaml 首启种子(幂等, 此后 DB 为唯一事实来源)

    from common.config.tasks import refresh_tasks_runtime
    await refresh_tasks_runtime()         # 段4: tasks 引擎参数快照(celery app 首建时用)

    await real.start_from_settings()      # 段5: cache/vector/graph 来自动态配置
    runtime.initialized = True
    logger.info("runtime 初始化完成: db_rel=yaml 引导, 其余配置=动态配置")
