"""
开发辅助模块配置
"""

from common.config.server import app
from fastapi import FastAPI
import logging

logger = logging.getLogger(__name__)

# 创建模块应用实例
module_app = FastAPI()

# 挂载到主应用
app.mount("/dev_tools", module_app)

logger.info("开发辅助模块配置完成")