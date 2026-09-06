from common.config.server import app
# lib
from fastapi import FastAPI
import logging
from sqlalchemy import inspect, text

from common.config.db import db_manager
from common.config.lifespan import register_init_hook

logger = logging.getLogger(__name__)

module_app = FastAPI()

app.mount("/file", module_app)

logger.info("ok...server module_file服务配置")


@register_init_hook
async def ensure_storage_ready():
    """启动时确保物理存储就绪: S3协议存储(rustfs/minio/s3)桶不存在时自动创建"""
    from module_file.config.filesystem import storage
    from module_file.utils.multi_storage.session.impl.storage_s3 import (
        S3StorageInterface,
    )

    if isinstance(storage, S3StorageInterface):
        try:
            await storage.ensure_bucket()
        except Exception as e:
            # 不阻断启动,上传时会再次暴露具体错误
            logger.warning(f"存储桶检查/自动创建失败: {e}")


@register_init_hook
async def ensure_file_entry_source_module():
    """存量表补列: file_entry.source_module(来源模块标记, 幂等; create_all 不为旧表加列)"""
    if db_manager.db_rel is None:
        return
    engine = db_manager.db_rel.engine
    async with engine.begin() as conn:
        cols = await conn.run_sync(
            lambda sc: {c["name"] for c in inspect(sc).get_columns("file_entry")}
        )
        if "source_module" not in cols:
            await conn.execute(
                text("ALTER TABLE file_entry "
                     "ADD COLUMN source_module VARCHAR(50) DEFAULT NULL")
            )
            logger.info("file_entry.source_module 来源模块列已补齐")