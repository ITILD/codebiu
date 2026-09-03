"""
搜索引擎工厂(注册表)

新增引擎步骤:
    1. 在 do.websearch.Engine 枚举追加引擎标识
    2. 在 engines 目录新建引擎文件,继承 base.SearchEngine 并实现 search 方法
    3. 在下方 ENGINE_CLASSES 列表追加引擎类
"""
from module_websearch.utils.websearch.base import SearchEngine
from module_websearch.utils.websearch.engines.duckduckgo import DuckDuckGoEngine
from module_websearch.utils.websearch.engines.firecrawl import FirecrawlEngine
from module_websearch.utils.websearch.engines.tavily import TavilyEngine

# 引擎注册表(顺序即 /engines 接口返回顺序)
ENGINE_CLASSES: list[type[SearchEngine]] = [
    DuckDuckGoEngine,
    TavilyEngine,
    FirecrawlEngine,
]
