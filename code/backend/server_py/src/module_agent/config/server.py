from common.config.server import app
from common.utils.fastapiEX.exceptions import BizFastAPI
from common.config.lifespan import register_init_hook
import logging

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
