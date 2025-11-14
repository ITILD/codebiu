import aiohttp
import asyncio

class WebConnectTestProxy:
    """使用aiohttp的简化版本"""

    @classmethod
    async def fetch_title_timeout(cls, url, timeout=5, proxy=None):
        """异步获取URL标题"""
        try:
            html = await cls.fetch_url_timeout(url, timeout, proxy)
            if html:
                start = html.find("<title>")
                end = html.find("</title>", start)
                if start == -1 or end == -1:
                    return None
                return html[start + 7 : end][:50]
        except Exception:
            return None

    @classmethod
    async def fetch_url_timeout(cls, url, timeout=5, proxy=None):
        """异步获取URL内容，带超时"""
        try:
            return await asyncio.wait_for(cls.fetch_url(url, proxy), timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Request to {url} timed out after {timeout} seconds")
        except Exception as e:
            raise type(e)(f"Failed to fetch {url}: {str(e)}") from e

    @classmethod
    async def fetch_url(cls, url, proxy=None):
        """使用aiohttp获取URL内容"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url, proxy=proxy) as response:
                return await response.text()


if __name__ == "__main__":

    async def main():
        test_urls = [
            "https://www.baidu.com",
            "https://www.google.com",
            "http://www.google.com",
            "https://github.com",
        ]

        # 测试不同代理配置
        proxy_configs = [
            None,  # 无代理
            "http://127.0.0.1:18081",  # HTTP代理
            "socks5://127.0.0.1:18080",  # SOCKS5代理
        ]

        for proxy in proxy_configs:
            print(f"\nTesting with proxy: {proxy}")

            tasks = []
            for url in test_urls:
                task = asyncio.create_task(
                    WebConnectTestProxy.fetch_title_timeout(url, 10, proxy)
                )
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)
            for url, result in zip(test_urls, results):
                if isinstance(result, Exception):
                    print(f"{url}: Error - {str(result)}")
                else:
                    print(f"{url}: {result}")

    asyncio.run(main())
