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
