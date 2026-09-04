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
async def ensure_model_config_scope_columns():
    """存量表补列: model_config 归属范围(scope/dept_id/is_default/display_name)与默认公共模型补全
    (create_all 不为旧表加列,幂等; 兼容旧 is_public 共享标记)"""
    if db_manager.db_rel is None:
        return
    engine = db_manager.db_rel.engine
    async with engine.begin() as conn:
        cols = await conn.run_sync(
            lambda sc: {c["name"] for c in inspect(sc).get_columns("model_config")}
        )
        if "scope" not in cols:
            await conn.execute(
                text("ALTER TABLE model_config ADD COLUMN scope VARCHAR(20) NOT NULL DEFAULT 'user'")
            )
        if "dept_id" not in cols:
            await conn.execute(
                text("ALTER TABLE model_config ADD COLUMN dept_id VARCHAR(64) NULL")
            )
        if "is_default" not in cols:
            await conn.execute(
                text("ALTER TABLE model_config ADD COLUMN is_default BOOLEAN NOT NULL DEFAULT FALSE")
            )
        if "display_name" not in cols:
            await conn.execute(
                text("ALTER TABLE model_config ADD COLUMN display_name VARCHAR(100) NULL")
            )
        # 旧数据迁移: 存在 is_public 时, is_public=True -> scope=public; False -> scope=user
        if "is_public" in cols:
            await conn.execute(
                text(
                    "UPDATE model_config SET scope = CASE WHEN is_public THEN 'public' ELSE 'user' END "
                    "WHERE scope = 'user' AND is_public = TRUE"
                )
            )
        logger.info("model_config 已补齐 scope/dept_id/is_default/display_name 归属字段")