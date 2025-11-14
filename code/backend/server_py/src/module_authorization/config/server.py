from common.config.server import app
# lib
from fastapi import FastAPI
import logging
# # 引入权限中间件
# from common.middleware.permission import PermissionMiddleware
# # 添加权限中间件
# app.add_middleware(PermissionMiddleware)

logger = logging.getLogger(__name__)

module_app = FastAPI()

app.mount("/authorization", module_app)

logger.info("module_authorization服务配置完成")