"""
搜索引擎抽象基类

每个引擎独立实现 search 方法,由 factory 注册表统一分发。
公共能力: HTTP 客户端构建、域名提取、屏蔽站点过滤。
"""
from abc import ABC, abstractmethod

import httpx

from module_websearch.config.settings import PROXY, REQUEST_TIMEOUT
from module_websearch.utils.websearch.do.websearch import DateRange, Engine, SearchResult

# 模拟浏览器请求头(搜索引擎普遍校验 UA)
BROWSER_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# API 类引擎通用 JSON 请求头
JSON_HEADERS: dict[str, str] = {"Content-Type": "application/json"}


class SearchEngine(ABC):
    """搜索引擎抽象基类:统一接口与HTTP客户端构建"""

    # 引擎唯一标识(注册表键,请求参数 engine 使用该值)
    name: Engine
    # 展示名称
    display_name: str = ""
    # 引擎说明
    description: str = ""
    # 是否需要 API Key
    requires_api_key: bool = False

    @abstractmethod
    async def search(
        self,
        query: str,
        limit: int,
        date_range: DateRange = DateRange.ANY,
        blocked_sites: list[str] | None = None,
    ) -> list[SearchResult]:
        """
        执行搜索
        :param query: 查询信息(句子或关键词)
        :param limit: 返回条数上限
        :param date_range: 时间范围限制
        :param blocked_sites: 屏蔽的站点域名列表(引擎不支持时自行在本地过滤)
        :return: 搜索结果列表
        """

    def is_configured(self) -> bool:
        """当前配置下引擎是否可用(需要 Key 的引擎检查 Key 是否已配置)"""
        return True

    # ############################# 通用工具 #############################

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

    @staticmethod
    def normalize_domains(sites: list[str] | None) -> list[str]:
        """
        归一化域名列表: 去协议头/路径/端口/空白,统一小写并去空去重
        :param sites: 原始域名列表(允许带 https://、路径等冗余)
        :return: 纯域名列表
        """
        normalized: list[str] = []
        for site in sites or []:
            host = site.strip().lower()
            if "://" in host:
                host = host.split("://", 1)[1]
            host = host.split("/", 1)[0].split(":", 1)[0]
            # 去掉首部点号与 www. 前缀,保证父域匹配(www.zhihu.com -> zhihu.com)
            host = host.lstrip(".")
            if host.startswith("www."):
                host = host[4:]
            if host and host not in normalized:
                normalized.append(host)
        return normalized

    @classmethod
    def filter_blocked(cls, results: list[SearchResult], blocked_sites: list[str] | None) -> list[SearchResult]:
        """
        按域名列表过滤结果(父域名匹配,example.com 会屏蔽 a.example.com)
        :param results: 待过滤结果
        :param blocked_sites: 屏蔽域名列表(未归一化)
        :return: 过滤后的结果
        """
        domains = cls.normalize_domains(blocked_sites)
        if not domains:
            return results
        kept: list[SearchResult] = []
        for item in results:
            host = cls.host_of(item.url).lower()
            if any(host == d or host.endswith(f".{d}") for d in domains):
                continue
            kept.append(item)
        return kept
