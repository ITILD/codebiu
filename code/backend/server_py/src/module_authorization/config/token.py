from common.utils.security.token_util import TokenConfig
# 从配置文件中读取token配置
from common.config.index import conf
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
