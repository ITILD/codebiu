from common.config.server import app
# lib
from common.utils.fastapiEX.exceptions import BizFastAPI
import logging

logger = logging.getLogger(__name__)

module_app = BizFastAPI()

app.mount("/graph", module_app)

logger.info("ok...server module_graph服务配置")
