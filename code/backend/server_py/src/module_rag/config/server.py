from common.config.server import app
from common.utils.fastapiEX.exceptions import BizFastAPI
import logging
from sqlalchemy import inspect, text

from common.config.db import db_manager
from common.config.lifespan import register_init_hook
# 导入即注册本模块权限声明到权限中心(rag 域)
from module_rag.config import permissions as rag_permissions  # noqa: F401
# 导入即注册本模块字典种子到字典中心(rag 域,与代码枚举对齐)
from module_rag.config import dict_seed as rag_dict_seed  # noqa: F401

logger = logging.getLogger(__name__)

module_app = BizFastAPI()

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
        # content_hash: 统一存储口径关联列(旧数据 NULL 走本地路径, 幂等补列)
        if "content_hash" not in cols:
            await conn.execute(
                text("ALTER TABLE project_document "
                     "ADD COLUMN content_hash VARCHAR(64) DEFAULT NULL")
            )
            await conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_project_document_content_hash "
                     "ON project_document (content_hash)")
            )
            logger.info("project_document.content_hash 内容哈希列已补齐")
        # entry_id: 条目级口径关联列(文档位于虚拟目录 /rag/<项目名>/ 下, 旧数据 NULL)
        if "entry_id" not in cols:
            await conn.execute(
                text("ALTER TABLE project_document "
                     "ADD COLUMN entry_id VARCHAR(50) DEFAULT NULL")
            )
            await conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_project_document_entry_id "
                     "ON project_document (entry_id)")
            )
            logger.info("project_document.entry_id 条目关联列已补齐")
        # project.root_entry_id: 项目根文件夹条目ID(惰性补建, 旧项目 NULL)
        pcols = await conn.run_sync(
            lambda sc: {c["name"] for c in inspect(sc).get_columns("project")}
        )
        if "root_entry_id" not in pcols:
            await conn.execute(
                text("ALTER TABLE project "
                     "ADD COLUMN root_entry_id VARCHAR(50) DEFAULT NULL")
            )
            logger.info("project.root_entry_id 项目根目录列已补齐")
