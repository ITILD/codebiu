import logging

from common.config.lifespan import register_init_hook

logger = logging.getLogger(__name__)


@register_init_hook
async def bootstrap_default_dicts():
    """幂等补齐注册中心声明的基础字典种子(sys 通用 + 各模块域,只补缺不覆盖)"""
    from module_main.config.dict_seed import ensure_default_dicts
    await ensure_default_dicts()
    logger.info("Default dicts bootstrap successfully.")


logger.info("ok...server module_main服务配置")
