from common.config.server import app
from fastapi import FastAPI
import logging

logger = logging.getLogger(__name__)

module_app = FastAPI()

app.mount("/nlp", module_app)

logger.info("ok...server module_nlp服务配置")