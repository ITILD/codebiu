from common.config.index import conf
from common.utils.security.token_util import TokenConfig
import logging
logger = logging.getLogger(__name__)
token_config: TokenConfig = None
if 'token' in conf and conf.token:
    token_config = TokenConfig(
        secret=conf.token.secret_key,
        algorithm=conf.token.algorithm,
        expire_minutes=conf.token.expire_minutes,
        refresh_expire_days=conf.token.refresh_expire_days,
    )
else:
    logger.error("token配置不存在")
