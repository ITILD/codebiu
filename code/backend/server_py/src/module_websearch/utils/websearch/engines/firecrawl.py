"""
Firecrawl 搜索引擎实现(搜索+可爬取,需 API Key)

文档: https://docs.firecrawl.dev
POST {api_base}/v1/search,Bearer 鉴权。
时间范围通过 tbs 参数(如 qdr:d)支持;屏蔽站点为本地过滤。
"""
from module_websearch.config.settings import FIRECRAWL_API_BASE, FIRECRAWL_API_KEY
from module_websearch.utils.websearch.base import JSON_HEADERS, SearchEngine
from module_websearch.utils.websearch.do.websearch import DateRange, Engine, SearchResult

# DateRange -> Firecrawl tbs 参数映射(google 风格 qdr:*,any 不传)
DATE_RANGE_PARAMS: dict[DateRange, str] = {
    DateRange.DAY: "qdr:d",
    DateRange.WEEK: "qdr:w",
    DateRange.MONTH: "qdr:m",
    DateRange.YEAR: "qdr:y",
}


class FirecrawlEngine(SearchEngine):
    """Firecrawl 引擎"""

    name = Engine.FIRECRAWL
    display_name = "Firecrawl"
    description = "搜索+网页抓取 API,支持时间范围,需 API Key"
    requires_api_key = True

    def is_configured(self) -> bool:
        """判断引擎是否已配置API Key(未配置时在引擎列表中置灰)"""
        return bool(FIRECRAWL_API_KEY)

    def _search_url(self) -> str:
        """拼接搜索端点(api_base 可指向自部署实例)"""
        return f"{FIRECRAWL_API_BASE}/v1/search"

    def _auth_headers(self) -> dict[str, str]:
        """构建带 Bearer Token 的请求头(Key 未配置时抛出异常)"""
        if not FIRECRAWL_API_KEY:
            raise ValueError("Firecrawl API Key 未配置,请在 config.yaml 的 websearch.firecrawl.api_key 中填写")
        return {**JSON_HEADERS, "Authorization": f"Bearer {FIRECRAWL_API_KEY}"}

    async def search(
        self,
        query: str,
        limit: int,
        date_range: DateRange = DateRange.ANY,
        blocked_sites: list[str] | None = None,
    ) -> list[SearchResult]:
        """
        执行 Firecrawl 搜索
        :param query: 查询信息(句子或关键词)
        :param limit: 返回条数上限
        :param date_range: 时间范围限制(映射 tbs 参数)
        :param blocked_sites: 屏蔽的站点域名列表(本地过滤)
        :return: 搜索结果列表
        """
        payload: dict = {"query": query, "limit": limit}
        tbs = DATE_RANGE_PARAMS.get(date_range)
        if tbs:
            payload["tbs"] = tbs

        async with self.build_client(headers=self._auth_headers()) as client:
            response = await client.post(self._search_url(), json=payload)
            response.raise_for_status()

        data = response.json()
        if not data.get("success", True):
            raise RuntimeError(f"Firecrawl 返回失败: {data.get('error') or data}")

        # 兼容两种返回结构: v1 为列表,新版可能为 {"web": [...]}
        items = data.get("data") or []
        if isinstance(items, dict):
            items = items.get("web") or []

        results: list[SearchResult] = []
        for item in items:
            url = str(item.get("url") or "")
            title = str(item.get("title") or "").strip()
            if not url or not title:
                continue
            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    description=str(item.get("description") or "").strip(),
                    source=self.host_of(url),
                    engine=self.name,
                    published_date=str(item.get("publishedDate") or ""),
                )
            )
        # Firecrawl 暂不支持 exclude 参数,统一本地过滤
        return self.filter_blocked(results, blocked_sites)[:limit]


if __name__ == "__main__":
    # 简单自测: python -m module_websearch.utils.websearch.engines.firecrawl "查询词"
    import asyncio
    import sys

    test_query = sys.argv[1] if len(sys.argv) > 1 else "fastapi"
    print(asyncio.run(FirecrawlEngine().search(test_query, 5)))
