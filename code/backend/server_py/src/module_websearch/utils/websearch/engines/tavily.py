"""
Tavily 搜索引擎实现(面向 AI 的搜索 API,需 API Key)

文档: https://docs.tavily.com
POST https://api.tavily.com/search,Bearer 鉴权。
原生支持 exclude_domains(屏蔽站点)与 time_range(时间范围)。
"""
from module_websearch.config.settings import TAVILY_API_KEY, TAVILY_INCLUDE_ANSWER, TAVILY_SEARCH_DEPTH
from module_websearch.utils.websearch.base import JSON_HEADERS, SearchEngine
from module_websearch.utils.websearch.do.websearch import DateRange, Engine, SearchResult

# Tavily 搜索端点
SEARCH_URL = "https://api.tavily.com/search"

# DateRange -> Tavily time_range 参数映射(any 不传)
DATE_RANGE_PARAMS: dict[DateRange, str] = {
    DateRange.DAY: "day",
    DateRange.WEEK: "week",
    DateRange.MONTH: "month",
    DateRange.YEAR: "year",
}


class TavilyEngine(SearchEngine):
    """Tavily 引擎"""

    name = Engine.TAVILY
    display_name = "Tavily"
    description = "AI 搜索 API,原生支持屏蔽站点与时间范围,需 API Key"
    requires_api_key = True

    def is_configured(self) -> bool:
        """判断引擎是否已配置API Key(未配置时在引擎列表中置灰)"""
        return bool(TAVILY_API_KEY)

    def _auth_headers(self) -> dict[str, str]:
        """构建带 Bearer Token 的请求头(Key 未配置时抛出异常)"""
        if not TAVILY_API_KEY:
            raise ValueError("Tavily API Key 未配置,请在 config.yaml 的 websearch.tavily.api_key 中填写")
        return {**JSON_HEADERS, "Authorization": f"Bearer {TAVILY_API_KEY}"}

    async def search(
        self,
        query: str,
        limit: int,
        date_range: DateRange = DateRange.ANY,
        blocked_sites: list[str] | None = None,
    ) -> list[SearchResult]:
        """
        执行 Tavily 搜索
        :param query: 查询信息(句子或关键词)
        :param limit: 返回条数上限
        :param date_range: 时间范围限制(映射 time_range 参数)
        :param blocked_sites: 屏蔽的站点域名列表(映射 exclude_domains 参数)
        :return: 搜索结果列表
        """
        payload: dict = {
            "query": query,
            "max_results": limit,
            "search_depth": TAVILY_SEARCH_DEPTH,
            "include_answer": TAVILY_INCLUDE_ANSWER,
        }
        time_range = DATE_RANGE_PARAMS.get(date_range)
        if time_range:
            payload["time_range"] = time_range
        domains = self.normalize_domains(blocked_sites)
        if domains:
            payload["exclude_domains"] = domains

        async with self.build_client(headers=self._auth_headers()) as client:
            response = await client.post(SEARCH_URL, json=payload)
            response.raise_for_status()

        data = response.json()
        results: list[SearchResult] = []
        for item in data.get("results") or []:
            url = str(item.get("url") or "")
            title = str(item.get("title") or "").strip()
            if not url or not title:
                continue
            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    description=str(item.get("content") or "").strip(),
                    source=self.host_of(url),
                    engine=self.name,
                    published_date=str(item.get("published_date") or ""),
                )
            )
        # Key 已配置给 exclude_domains,这里兜底再做一次本地过滤(极端情况)
        return self.filter_blocked(results, blocked_sites)[:limit]


if __name__ == "__main__":
    # 简单自测: python -m module_websearch.utils.websearch.engines.tavily "查询词"
    import asyncio
    import sys

    test_query = sys.argv[1] if len(sys.argv) > 1 else "fastapi"
    print(asyncio.run(TavilyEngine().search(test_query, 5)))
