"""
搜索引擎注册表

新增引擎步骤:
    1. 在本目录新建引擎文件,继承 base.SearchEngine 并实现 search 方法
    2. 在下方 ENGINE_CLASSES 列表追加引擎类
"""
from module_websearch.utils.engines.base import SearchEngine
from module_websearch.utils.engines.bing import BingEngine
from module_websearch.utils.engines.duckduckgo import DuckDuckGoEngine

# 引擎注册表(顺序即 /engines 接口返回顺序)
ENGINE_CLASSES: list[type[SearchEngine]] = [
    DuckDuckGoEngine,
    BingEngine,
]
