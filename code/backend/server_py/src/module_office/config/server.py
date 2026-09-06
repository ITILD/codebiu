from common.config.server import app
# lib
from common.utils.fastapiEX.exceptions import BizFastAPI
import logging

logger = logging.getLogger(__name__)

module_app = BizFastAPI()

app.mount("/office", module_app)

logger.info("module_office服务配置完成")
