from contextlib import asynccontextmanager
from fastapi import FastAPI
from common.config.index import conf
from common.config.db import db_manager
import logging

logger = logging.getLogger(__name__)


async def server_start():
    logger.info("server_start...")
    try:
        await db_manager.connect_all()
        # 尝试启用 PostGIS 空间扩展(geo_feature 表建表前必须已启用, 失败仅告警)
        try:
            if db_manager.db_rel:
                await db_manager.db_rel.exec("CREATE EXTENSION IF NOT EXISTS postgis")
                logger.info("PostGIS extension ready.")
        except Exception as e:
            logger.warning(f"PostGIS extension init failed: {e}")
        await db_manager.table_create_all()
        logger.info("Database tables init successfully.")
    except Exception as e:
        logger.error(f"server_start error: {e}")
    
    # 初始化 Casbin 权限策略
    try:
        # 延迟导入避免循环依赖
        from module_authorization.config.casbin_rule import auth_manager
        await auth_manager.init_default_casbin()
        logger.info("Casbin policy init successfully.")
    except Exception as e:
        logger.warning(f"Casbin init failed: {e}")

    # 引导系统默认管理员账户(config.dev.yaml 的 admin 段,拥有全部权限)
    try:
        # 延迟导入避免循环依赖
        from module_authorization.service.bootstrap import BootstrapService
        from module_authorization.dao.user import UserDao
        await BootstrapService(UserDao()).ensure_default_admin()
        logger.info("Default admin bootstrap successfully.")
    except Exception as e:
        logger.warning(f"Default admin bootstrap failed: {e}")

    # 引导基础字典种子数据(sys 通用字典 + 各模块域字典,批量幂等补缺)
    try:
        # 延迟导入避免循环依赖
        from module_main.service.bootstrap import DictBootstrapService
        await DictBootstrapService().ensure_default_dicts()
        logger.info("Default dicts bootstrap successfully.")
    except Exception as e:
        logger.warning(f"Default dicts bootstrap failed: {e}")


async def server_end():
    logger.info("server_end...")
    # redis持久化 英文
    await db_manager.shutdown()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    await server_start()
    yield
    # 关闭时执行
    await server_end()
