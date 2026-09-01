"""
Bing 搜索引擎实现(网页解析方式,无需 API 密钥)

请求 bing.com/search 网页端点,解析 li.b_algo 结果块。
国内网络可能较慢或需要代理(可在 config.yaml 的 websearch.proxy 配置)。
"""
from bs4 import BeautifulSoup

from module_websearch.utils.websearch.base import SearchEngine
from module_websearch.utils.websearch.do.websearch import Engine, SearchResult

# Bing 网页搜索端点
SEARCH_URL = "https://www.bing.com/search"


class BingEngine(SearchEngine):
    """Bing 引擎"""

    name = Engine.BING
    display_name = "Bing"
    description = "微软必应,网页解析方式无需密钥"

    async def search(self, query: str, limit: int) -> list[SearchResult]:
        """
        执行 Bing 搜索
        :param query: 查询词
        :param limit: 返回条数上限
        :return: 搜索结果列表
        """
        results: list[SearchResult] = []
        async with self.build_client() as client:
            response = await client.get(
                SEARCH_URL,
                params={
                    "q": query,
                    # count 控制单页条数,first 为偏移(取1即可,首页足够)
                    "count": min(limit, 30),
                    "first": 1,
                    "mkt": "zh-CN",
                },
            )
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")
        for item in soup.select("li.b_algo"):
            if len(results) >= limit:
                break
            link_el = item.select_one("h2 a")
            if not link_el:
                continue
            title = link_el.get_text(strip=True)
            url = link_el.get("href", "")
            if not title or not url or not url.startswith("http"):
                continue
            # 摘要优先取 b_caption 内的 p 标签
            snippet_el = item.select_one(".b_caption p") or item.select_one("p")
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


if __name__ == "__main__":
    # 简单自测: python -m module_websearch.utils.websearch.engines.bing "查询词"
    import asyncio
    import sys

    test_query = sys.argv[1] if len(sys.argv) > 1 else "fastapi"
    print(asyncio.run(BingEngine().search(test_query, 5)))
