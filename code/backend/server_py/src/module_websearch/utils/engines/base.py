"""
搜索引擎抽象基类

参考 open-webSearch 的引擎(engine)分层思路:
每个引擎独立实现 search 方法,由 Service 层注册表统一分发。
"""
from abc import ABC, abstractmethod

import httpx

from module_websearch.config.settings import PROXY, REQUEST_TIMEOUT
from module_websearch.do.websearch import SearchResult

# 模拟浏览器请求头(搜索引擎普遍校验 UA)
BROWSER_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


class SearchEngine(ABC):
    """搜索引擎抽象基类:统一接口与HTTP客户端构建"""

    # 引擎唯一标识(注册表键,请求参数 engine 使用该值)
    name: str = ""
    # 展示名称
    display_name: str = ""
    # 引擎说明
    description: str = ""

    @abstractmethod
    async def search(self, query: str, limit: int) -> list[SearchResult]:
        """
        执行搜索
        :param query: 查询词
        :param limit: 返回条数上限
        :return: 搜索结果列表
        """

    @staticmethod
    def build_client(
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        proxy: str | None = None,
    ) -> httpx.AsyncClient:
        """
        构建异步HTTP客户端(统一超时与代理配置)
        :param headers: 附加请求头(默认合并浏览器UA)
        :param timeout: 超时秒数(默认取模块配置)
        :param proxy: 代理地址(None 时取模块配置,空串表示强制直连)
        """
        merged_headers = {**BROWSER_HEADERS, **(headers or {})}
        # 代理优先级: 显式参数 > 模块配置
        effective_proxy = proxy if proxy is not None else PROXY
        client_kwargs: dict = {
            "headers": merged_headers,
            "timeout": timeout or REQUEST_TIMEOUT,
            "follow_redirects": True,
        }
        if effective_proxy:
            client_kwargs["proxy"] = effective_proxy
        return httpx.AsyncClient(**client_kwargs)

    @staticmethod
    def host_of(url: str) -> str:
        """提取链接的站点域名(用作来源字段)"""
        try:
            return httpx.URL(url).host or ""
        except Exception:
            return ""
