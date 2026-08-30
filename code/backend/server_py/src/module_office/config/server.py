from common.config.server import app
# lib
from fastapi import FastAPI
import logging

logger = logging.getLogger(__name__)

module_app = FastAPI()

app.mount("/office", module_app)

logger.info("module_office服务配置完成")
