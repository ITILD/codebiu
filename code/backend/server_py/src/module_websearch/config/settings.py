"""
网页搜索模块配置

从 config.yaml 的 websearch 段读取,缺失时使用内置默认值:
    websearch:
      default_engine: duckduckgo   # 默认引擎(本地直连,无需密钥)
      timeout: 15                  # 请求超时(秒)
      max_results: 10              # 默认返回条数上限
      proxy: null                  # 可选代理(如 http://127.0.0.1:7890)
"""
from common.config.index import conf
from module_websearch.utils.websearch.do.websearch import Engine
import logging

logger = logging.getLogger(__name__)

# 从 config.yaml 读取 websearch 配置(可选,缺失时使用默认值)
try:
    conf_websearch = conf.websearch
    if conf_websearch is None:
        conf_websearch = {}
except Exception:
    conf_websearch = {}

# 默认搜索引擎标识(与 utils/websearch/factory.py 注册表中的 name 对应,非法值回退 DuckDuckGo)
try:
    DEFAULT_ENGINE: Engine = Engine(conf_websearch.get("default_engine", "duckduckgo"))
except ValueError:
    logger.warning(f"websearch.default_engine 非法值,回退默认引擎: {conf_websearch.get('default_engine')}")
    DEFAULT_ENGINE = Engine.DUCKDUCKGO
# HTTP 请求超时(秒)
REQUEST_TIMEOUT: float = float(conf_websearch.get("timeout", 15))
# 默认返回结果条数上限
MAX_RESULTS: int = int(conf_websearch.get("max_results", 10))
# 出网代理(为空表示直连;国内访问 bing/duckduckgo 可按需配置)
PROXY: str | None = conf_websearch.get("proxy") or None

logger.info("ok...websearch 网页搜索配置加载完成")
