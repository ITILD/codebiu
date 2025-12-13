import asyncio
import ssl
from urllib.parse import urlparse
import socket


class WebConnectTestNative:
    """标准库支持的检测,防止内网环境连通性测试配置困难"""
    @classmethod
    async def fetch_title_timeout(cls, url, port=None, timeout=5):
        try:
            html = await cls.fetch_url_timeout(url, port, timeout)
            if html:
                start = html.find("<title>")
                end = html.find("</title>", start)  # 从 start 开始查找
                if start == -1 or end == -1:
                    return
                title = html[start + 7 : end][:50]
                return title
        except Exception:
            return

    @classmethod
    async def fetch_url_timeout(cls, url, port=None, timeout=5):
        """异步获取URL内容，并设置超时时间"""
        try:
            result = await asyncio.wait_for(cls.fetch_url(url, port), timeout)
            return result
        except TimeoutError:
            # Re-raise with a more descriptive message
            raise TimeoutError(f"Request to {url} timed out after {timeout} seconds")
        except Exception as e:
            # Add context to any other errors
            raise type(e)(f"Failed to fetch {url}: {str(e)}") from e

    @classmethod
    async def fetch_url(cls, url, port=None, encoding: str = "utf-8"):
        # 解析URL
        parsed = urlparse(url)
        host = parsed.hostname
        path = parsed.path if parsed.path else "/"

        # 自动确定端口和SSL
        if port is None:
            if parsed.port:
                port = parsed.port
            elif parsed.scheme == "https":
                port = 443
            else:
                port = 80
        # 创建SSL上下文(如果需要)
        ssl_context = None
        if parsed.scheme == "https":
            ssl_context = ssl.create_default_context()
        # print(f"Connecting to {host}:{port} {ssl_context}")
        # 建立连接
        reader, writer = await asyncio.open_connection(
            host=host, port=port, ssl=ssl_context, proto=socket.IPPROTO_TCP
        )

        try:
            # 发送HTTP请求
            request = (
                f"GET {path} HTTP/1.1\r\n"
                f"Host: {host}\r\n"
                "User-Agent: Python-asyncio\r\n"
                "Connection: close\r\n\r\n"
            )
            writer.write(request.encode())
            await writer.drain()

            # 读取响应头
            headers = await reader.readuntil(b"\r\n\r\n")

            # 检查是否为分块传输编码
            if b"Transfer-Encoding: chunked" in headers:
                body = await cls.read_chunked(reader)
            else:
                body = await reader.read()

            return body.decode(encoding, errors="ignore")

        finally:
            writer.close()
            await writer.wait_closed()

    @classmethod
    async def read_chunked(cls, reader):
        """处理分块传输编码"""
        data = []
        while True:
            chunk_size_line = await reader.readuntil(b"\r\n")
            chunk_size = int(chunk_size_line.strip(), 16)
            if chunk_size == 0:
                break
            data.append(await reader.readexactly(chunk_size))
            await reader.read(2)  # 跳过\r\n
        return b"".join(data)


if __name__ == "__main__":

    async def main():
        # curl https://www.google.com.hk
        # 测试不同场景
        test_urls = [
            ("https://www.baidu.com", None),  # 自动判断(https)
            # ("https://www.baidu.com:443", None),  # 自动判断(https)
            ("https://www.google.com", None),  # 自动判断(https)
            ("http://www.google.com", None),  # 自动判断(https)
            # ("http://example.com", 80),  # 明确指定不使用SSL
            ("https://github.com", 443),  # 明确指定使用SSL
            # ("http://example.org", None),  # 自动判断(http)
        ]

        # 创建任务列表
        tasks = []
        for url, port in test_urls:
            # print(f"Preparing to fetch {url} (port={port})")
            task = asyncio.create_task(
                WebConnectTestNative.fetch_title_timeout(url, port, 10)
            )
            tasks.append(task)

        # 并发执行所有任务
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for (url, port), result in zip(test_urls, results):
            print(f"\n{url} (port={port}): {result}")

    asyncio.run(main())
