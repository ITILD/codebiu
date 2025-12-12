from contextlib import asynccontextmanager
from fastapi import FastAPI
from common.config import db
import logging

from module_main.service.db import TableService
logger = logging.getLogger(__name__)

async def server_start():
    logger.info("server_start...")
    try:
        await TableService.create()
        logger.info("Database tables init successfully.")
        # Milvus
        await db.db_vector.connect()
    except Exception as e:
        logger.error(f"server_start error: {e}")
        
async def server_end():
    logger.info("server_end...")
    # redis持久化 英文
    
    


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    await server_start()
    yield
    # 关闭时执行
    await server_end()