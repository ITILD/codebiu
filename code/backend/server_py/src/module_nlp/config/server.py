from common.config.server import app
from common.utils.fastapiEX.exceptions import BizFastAPI
import logging

logger = logging.getLogger(__name__)

module_app = BizFastAPI()

app.mount("/nlp", module_app)

logger.info("ok...server module_nlp服务配置")