from common.config.server import app
from fastapi import FastAPI
import logging

logger = logging.getLogger(__name__)

module_app = FastAPI()

app.mount("/rag", module_app)

logger.info("module_rag服务配置完成")
