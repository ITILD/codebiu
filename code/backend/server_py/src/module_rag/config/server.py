from common.config.server import app
from fastapi import FastAPI
import logging
from sqlalchemy import inspect, text

from common.config.db import db_manager
from common.config.lifespan import register_init_hook
# 导入即注册本模块权限声明到权限中心(rag 域)
from module_rag.config import permissions as rag_permissions  # noqa: F401
# 导入即注册本模块字典种子到字典中心(rag 域,与代码枚举对齐)
from module_rag.config import dict_seed as rag_dict_seed  # noqa: F401

logger = logging.getLogger(__name__)

module_app = FastAPI()

app.mount("/rag", module_app)

logger.info("module_rag服务配置完成")


@register_init_hook
async def ensure_project_document_parse_steps():
    """存量表补列: project_document.parse_steps(入库步骤进度 JSONB, 幂等;
    create_all 不为旧表加列)"""
    if db_manager.db_rel is None:
        return
    engine = db_manager.db_rel.engine
    async with engine.begin() as conn:
        cols = await conn.run_sync(
            lambda sc: {c["name"] for c in inspect(sc).get_columns("project_document")}
        )
        if "parse_steps" not in cols:
            await conn.execute(
                text("ALTER TABLE project_document "
                     "ADD COLUMN parse_steps JSONB NOT NULL DEFAULT '{}'")
            )
            logger.info("project_document.parse_steps 步骤进度列已补齐")
