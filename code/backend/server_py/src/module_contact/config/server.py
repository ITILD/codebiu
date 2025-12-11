from common.config.server import app
# lib
from fastapi import FastAPI
import logging

logger = logging.getLogger(__name__)

module_app = FastAPI()

app.mount("/contact", module_app)

logger.info("ok...server module_contact 联系方式_服务配置")
