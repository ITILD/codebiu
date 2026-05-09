from common.config.server import app
# lib
from fastapi import FastAPI
import logging

logger = logging.getLogger(__name__)

module_app = FastAPI()

app.mount("/life", module_app)

logger.info("ok...server module_life服务配置")