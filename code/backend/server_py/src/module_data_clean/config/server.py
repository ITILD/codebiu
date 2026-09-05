from common.config.server import app
# lib
from fastapi import FastAPI
import logging

logger = logging.getLogger(__name__)

module_app = FastAPI()

app.mount("/data-clean", module_app)

logger.info("ok...server module_data_clean服务配置")
