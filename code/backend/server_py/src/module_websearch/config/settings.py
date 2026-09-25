"""网页搜索模块配置(动态): 各消费点经 get_websearch_settings() 按调用时读取"""
from common.config.dynamic import get_settings
from common.config.dynamic.schemas import WebSearchSettings


async def get_websearch_settings() -> WebSearchSettings:
    """读取当前网页搜索配置(TTL 缓存内直返; 配置中心变更即时生效)"""
    return await get_settings(WebSearchSettings)
