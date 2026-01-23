from common.config.server import app
# lib
from fastapi import FastAPI
import logging

logger = logging.getLogger(__name__)

module_app = FastAPI()

app.mount("/graph", module_app)

logger.info("ok...server module_graph服务配置")
