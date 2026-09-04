from common.config.server import app
# lib
from fastapi import FastAPI
import logging
from sqlalchemy import inspect, text

from common.config.db import db_manager
from common.config.lifespan import register_init_hook

logger = logging.getLogger(__name__)

module_app = FastAPI()

app.mount("/ai", module_app)

logger.info("ok...server module_ai服务配置")


@register_init_hook
async def ensure_model_config_is_public():
    """存量表补列: model_config.is_public 共享标记(create_all 不为旧表加列,幂等)"""
    if db_manager.db_rel is None:
        return
    engine = db_manager.db_rel.engine
    async with engine.begin() as conn:
        cols = await conn.run_sync(
            lambda sc: [c["name"] for c in inspect(sc).get_columns("model_config")]
        )
        if "is_public" not in cols:
            await conn.execute(
                text("ALTER TABLE model_config ADD COLUMN is_public BOOLEAN NOT NULL DEFAULT FALSE")
            )
            logger.info("model_config 已补列 is_public(共享标记)")