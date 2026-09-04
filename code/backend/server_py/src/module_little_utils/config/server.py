from common.config.server import app
# lib
from fastapi import FastAPI
import logging

logger = logging.getLogger(__name__)

module_app = FastAPI()

app.mount("/little-utils", module_app)

logger.info("ok...server module_little_utils服务配置")
