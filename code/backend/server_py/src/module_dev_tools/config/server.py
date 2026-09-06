"""
开发辅助模块配置
"""

from common.config.server import app
from common.utils.fastapiEX.exceptions import BizFastAPI
import logging

logger = logging.getLogger(__name__)

# 创建模块应用实例
module_app = BizFastAPI()

# 挂载到主应用
app.mount("/dev-tools", module_app)

logger.info("开发辅助模块配置完成")