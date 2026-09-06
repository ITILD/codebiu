from common.config.server import app
# lib
from common.utils.fastapiEX.exceptions import BizFastAPI
import logging

logger = logging.getLogger(__name__)

module_app = BizFastAPI()

app.mount("/template", module_app)

logger.info("ok...server module_template服务配置")
