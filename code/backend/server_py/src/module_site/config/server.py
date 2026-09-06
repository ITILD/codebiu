from common.config.server import app
from common.utils.fastapiEX.exceptions import BizFastAPI
import logging
from sqlalchemy import Enum as SAEnum, inspect, text

from common.config.db import db_manager
from common.config.lifespan import register_init_hook
# 导入即注册本模块权限声明到权限中心(site 域: 博客/备忘/记账)
from module_site.config import permissions as site_permissions  # noqa: F401

logger = logging.getLogger(__name__)

module_app = BizFastAPI()

app.mount("/site", module_app)

logger.info("ok...server module_site服务配置")