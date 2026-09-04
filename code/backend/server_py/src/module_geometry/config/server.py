from fastapi import FastAPI
import logging

from common.config.db import db_manager
from common.config.lifespan import register_init_hook, register_startup_hook
from common.config.server import app

logger = logging.getLogger(__name__)

# 模块子应用(挂载到主应用 /geometry 路径下)
module_app = FastAPI()
app.mount("/geometry", module_app)

# 导入权限声明(注册到权限中心, 幂等)
from module_geometry.config.permissions import GEOMETRY_DEFINE  # noqa: F401, E402


@register_startup_hook
async def enable_postgis():
    """启用 PostGIS 空间扩展(geo_feature 的 geometry 列依赖该类型,须先于建表)"""
    if db_manager.db_rel:
        await db_manager.db_rel.exec("CREATE EXTENSION IF NOT EXISTS postgis")
        logger.info("PostGIS extension ready.")


@register_init_hook
async def ensure_geo_feature_style_column():
    """存量表补列: geo_feature.style 渲染样式列(create_all 不会为旧表新增列, 幂等)"""
    if db_manager.db_rel:
        await db_manager.db_rel.exec(
            "ALTER TABLE geo_feature ADD COLUMN IF NOT EXISTS style JSONB"
        )
        logger.info("geo_feature.style column ready.")


logger.info("ok...server module_geometry服务配置")
