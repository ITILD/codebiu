from common.config.server import app
# lib
from common.utils.fastapiEX.exceptions import BizFastAPI
import logging

logger = logging.getLogger(__name__)

module_app = BizFastAPI()

app.mount("/contact", module_app)

logger.info("ok...server module_contact 联系方式_服务配置")
