from common.config.server import app
from common.utils.fastapiEX.exceptions import BizFastAPI
from common.config.lifespan import register_init_hook
import logging
from sqlalchemy import inspect, text

from common.config.db import db_manager

# 导入即注册本模块权限声明到权限中心(agent 域)
from module_agent.config import permissions as agent_permissions  # noqa: F401

logger = logging.getLogger(__name__)

module_app = BizFastAPI()

app.mount("/agent", module_app)

logger.info("module_agent服务配置完成")


@register_init_hook
async def seed_builtin_agents():
    """启动时幂等写入内置公共智能体(翻译/写作/代码, 已存在则跳过)"""
    from module_agent.service.agent import AgentService

    await AgentService().seed_builtin_agents()


@register_init_hook
async def ensure_agent_struct_columns():
    """存量表补列: agent 结构体配置 4 列(幂等; create_all 不为旧表加列)"""
    if db_manager.db_rel is None:
        return
    engine = db_manager.db_rel.engine
    async with engine.begin() as conn:
        cols = await conn.run_sync(
            lambda sc: {c["name"] for c in inspect(sc).get_columns("agent")}
        )
        if "input_type" not in cols:
            await conn.execute(
                text("ALTER TABLE agent "
                     "ADD COLUMN input_type VARCHAR(8) NOT NULL DEFAULT 'str'")
            )
            logger.info("agent.input_type 输入类型列已补齐")
        if "output_type" not in cols:
            await conn.execute(
                text("ALTER TABLE agent "
                     "ADD COLUMN output_type VARCHAR(8) NOT NULL DEFAULT 'str'")
            )
            logger.info("agent.output_type 输出类型列已补齐")
        if "input_schema" not in cols:
            await conn.execute(
                text("ALTER TABLE agent ADD COLUMN input_schema JSONB NULL")
            )
            logger.info("agent.input_schema 输入结构列已补齐")
        if "output_schema" not in cols:
            await conn.execute(
                text("ALTER TABLE agent ADD COLUMN output_schema JSONB NULL")
            )
            logger.info("agent.output_schema 输出结构列已补齐")


@register_init_hook
async def ensure_agent_workflow_columns():
    """存量表补列: 工作流智能体(agent.agent_type/agent.workflow) + 运行轨迹(agent_run.trace)"""
    if db_manager.db_rel is None:
        return
    engine = db_manager.db_rel.engine
    async with engine.begin() as conn:
        agent_cols = await conn.run_sync(
            lambda sc: {c["name"] for c in inspect(sc).get_columns("agent")}
        )
        if "agent_type" not in agent_cols:
            await conn.execute(
                text("ALTER TABLE agent "
                     "ADD COLUMN agent_type VARCHAR(12) NOT NULL DEFAULT 'simple'")
            )
            logger.info("agent.agent_type 智能体类型列已补齐")
        if "workflow" not in agent_cols:
            await conn.execute(
                text("ALTER TABLE agent ADD COLUMN workflow JSONB NULL")
            )
            logger.info("agent.workflow 工作流图列已补齐")
        run_cols = await conn.run_sync(
            lambda sc: {c["name"] for c in inspect(sc).get_columns("agent_run")}
        )
        if "trace" not in run_cols:
            await conn.execute(
                text("ALTER TABLE agent_run ADD COLUMN trace JSONB NULL")
            )
            logger.info("agent_run.trace 运行轨迹列已补齐")
