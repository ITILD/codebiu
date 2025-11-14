from common.config.index import conf
import logging

from common.utils.net.connect.proxy_manager import ProxyManager
logger = logging.getLogger(__name__)
http_proxy = None
# HTTP代理
if conf.get("proxy"):
    logger.info("=== HTTP代理 ===")
    try:
        # 根据配置创建代理管理器
        proxy_url = f"{conf.proxy.type}://{conf.proxy.host}:{conf.proxy.port}"
        http_proxy = ProxyManager(proxy_url, conf.proxy.type)
        http_proxy.test_proxy()
    except Exception as e:
        logger.error(f"代理配置失败: {e}")
        http_proxy = None