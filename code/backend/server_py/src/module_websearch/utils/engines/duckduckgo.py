"""
DuckDuckGo 搜索引擎实现(默认引擎,本地直连无需密钥)

使用 html.duckduckgo.com/html/ 端点 POST 查询,
返回经典 HTML 结构,BeautifulSoup 解析结果块。
"""
from urllib.parse import parse_qs, unquote, urlparse

from bs4 import BeautifulSoup

from module_websearch.do.websearch import SearchResult
from module_websearch.utils.engines.base import SearchEngine

# DDG 轻量 HTML 端点(无 JS 依赖,适合服务端解析)
SEARCH_URL = "https://html.duckduckgo.com/html/"


class DuckDuckGoEngine(SearchEngine):
    """DuckDuckGo 引擎"""

    name = "duckduckgo"
    display_name = "DuckDuckGo"
    description = "默认引擎,本地直连无需密钥"

    async def search(self, query: str, limit: int) -> list[SearchResult]:
        """
        执行 DuckDuckGo 搜索
        :param query: 查询词
        :param limit: 返回条数上限
        :return: 搜索结果列表
        """
        results: list[SearchResult] = []
        async with self.build_client() as client:
            # 分页参数 s 为偏移量,单页约25条,一般一页即可满足 limit
            response = await client.post(
                SEARCH_URL,
                data={"q": query, "kl": "wt-wt"},
            )
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")
        for item in soup.select("div.result"):
            if len(results) >= limit:
                break
            link_el = item.select_one("a.result__a")
            if not link_el:
                continue
            title = link_el.get_text(strip=True)
            raw_url = link_el.get("href", "")
            url = self._clean_url(raw_url)
            # 跳过广告与无效链接
            if not title or not url or "result--ad" in item.get("class", []):
                continue
            snippet_el = item.select_one(".result__snippet")
            description = snippet_el.get_text(strip=True) if snippet_el else ""
            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    description=description,
                    source=self.host_of(url),
                    engine=self.name,
                )
            )
        return results[:limit]

    @staticmethod
    def _clean_url(raw_url: str) -> str:
        """
        清洗 DDG 跳转链接为真实地址
        DDG 返回形如 //duckduckgo.com/l/?uddg=<编码后真实URL>&rut=... 的跳转链
        :param raw_url: 原始 href
        :return: 真实 URL(无法解析时原样返回)
        """
        if not raw_url:
            return ""
        if raw_url.startswith("//"):
            raw_url = "https:" + raw_url
        parsed = urlparse(raw_url)
        hostname = parsed.hostname or ""
        if "duckduckgo.com" in hostname and parsed.path == "/l/":
            uddg = parse_qs(parsed.query).get("uddg", [])
            if uddg:
                return unquote(uddg[0])
        return raw_url
