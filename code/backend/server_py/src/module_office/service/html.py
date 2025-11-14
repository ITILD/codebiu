from playwright.async_api import async_playwright
from module_office.do.html import HtmlSearchConfigBase, SearchResult
import aiohttp  # uv add brotlicffi
from bs4 import BeautifulSoup


class HtmlService:
    """使用本机 Edge 浏览器操作网页的 HTML 服务类"""

    def __init__(self, html_search_config: HtmlSearchConfigBase = None):
        self.html_search_config = html_search_config or HtmlSearchConfigBase()

    async def search_playwright(
        self,
        keyword: str,
    ) -> str:
        """在指定搜索引擎搜索指定关键词并返回结果文本"""
        base_search_url: str = await self._build_search_url(keyword)
        async with async_playwright() as p:
            browser = None
            try:
                # 启动本机 Edge 浏览器（无头模式）
                browser = await p.chromium.launch(
                    # playwright install chromium 可以不指定
                    # channel=BrowserType.EDGE,
                    # headless=False,  # ← 无头模式
                    # slow_mo=100,  # 慢速模式，用于调试
                    args=["--disable-gpu", "--no-sandbox"],
                )
                page = await browser.new_page()
                page.set_default_timeout(30000)

                # 访问搜索页面并查询
                # await page.goto(base_search_url, wait_until="networkidle")
                await page.goto(base_search_url, wait_until="load")  # 不再等 networkidle

                # 等待结果加载
                await page.wait_for_load_state("networkidle")
                await page.wait_for_selector(
                    self.html_search_config.elements_selector, state="visible"
                )

                # 分块提取结果文本 SearchResult
                results: list[SearchResult] = []
                # 提取结果文本
                # 提取所有搜索结果项（根据实际 HTML 调整 selector）
                result_elements = await page.query_selector_all(
                    self.html_search_config.elements_selector
                )  # 示例选择器
                for elem in result_elements:
                    # 标题节点
                    title_elem = await elem.query_selector(
                        self.html_search_config.title_selector
                    )  # 假设标题在 h3 > a 中
                    url = await title_elem.get_attribute("href") if title_elem else None
                    title = await title_elem.inner_text() if title_elem else None

                    # 摘要节点
                    snippet_elem = await elem.query_selector(
                        self.html_search_config.snippet_selector
                    )
                    snippet = await snippet_elem.inner_text() if snippet_elem else None

                    results.append(SearchResult(title=title, url=url, snippet=snippet))

                return results

            except Exception as e:
                return f"搜索过程中发生错误: {str(e)}"
            finally:
                if browser:
                    await browser.close()

    async def search_bs4(self, keyword: str):
        base_search_url: str = await self._build_search_url(keyword)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30.0),  # 单位是秒，不是毫秒！
            headers=headers,
        ) as session:
            async with session.get(base_search_url) as response:
                html = await response.text()
                soup = BeautifulSoup(html, "lxml")
                # 检查是否触发百度安全验证
                if soup.title and "百度安全验证" in soup.title.text:
                    raise RuntimeError("触发百度安全验证，请检查请求头或使用代理")
                return soup

    async def _build_search_url(self, keyword: str):
        # 访问搜索引擎首页
        base_search_url = self.html_search_config.base_url
        # 检索词
        base_search_url += keyword
        # 拼接排除的网址
        for exclude_url in self.html_search_config.exclude_url_list:
            base_search_url += (
                f" {self.html_search_config.exclude_method}{exclude_url}"
            )
        return base_search_url


if __name__ == "__main__":
    import asyncio

    async def main():
        html_search_config = HtmlSearchConfigBase(
            base_url="https://cn.bing.com/search?q=",
            exclude_method="-site:",
            exclude_url_list=["csdn.net"],
            elements_selector="#b_results .b_algo",
            title_selector="h2 a",
            snippet_selector="p",
        )
        # html_search_config = None
        service = HtmlService(html_search_config)
        result = await service.search_playwright("python 异步")
        # result = await service.search_bs4("python 异步")
        print(result)

    asyncio.run(main())
