from fastapi import FastAPI
import logging

from common.config.server import app

logger = logging.getLogger(__name__)

# 模块子应用(挂载到主应用 /geometry 路径下)
module_app = FastAPI()
app.mount("/geometry", module_app)

# 导入权限声明(注册到权限中心, 幂等)
from module_geometry.config.permissions import GEOMETRY_DEFINE  # noqa: F401, E402

logger.info("ok...server module_geometry服务配置")
