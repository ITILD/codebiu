import os
import requests
import logging
logger = logging.getLogger(__name__)

class ProxyManager:
    """支持HTTP和SOCKS代理的简化版代理管理器"""

    def __init__(self, proxy_url=None, proxy_type="http"):
        """备份原始环境变量"""
        self.proxy_url = proxy_url
        self.proxy_type = proxy_type
        self.original_http = os.environ.get("HTTP_PROXY")
        self.original_https = os.environ.get("HTTPS_PROXY")
        self.original_all = os.environ.get("ALL_PROXY")

        if proxy_url:
            self.set_proxy()

    def set_proxy(self):
        """设置代理"""
        if not self.proxy_url:
            return

        if self.proxy_type == "http":
            os.environ["HTTP_PROXY"] = self.proxy_url
            os.environ["HTTPS_PROXY"] = self.proxy_url
        elif self.proxy_type == "socks":
            # 处理socks代理
            socks_url = (
                self.proxy_url.replace("socks://", "")
                if self.proxy_url.startswith("socks://")
                else self.proxy_url
            )
            socks_proxy = f"socks5://{socks_url}"
            os.environ["ALL_PROXY"] = socks_proxy
            os.environ["HTTP_PROXY"] = socks_proxy
            os.environ["HTTPS_PROXY"] = socks_proxy

        logger.info(f"{self.proxy_type.upper()}代理已设置: {self.proxy_url}")

    def clear_proxy(self):
        """清除代理"""
        # 恢复原始设置
        if self.original_http:
            os.environ["HTTP_PROXY"] = self.original_http
        elif "HTTP_PROXY" in os.environ:
            del os.environ["HTTP_PROXY"]

        if self.original_https:
            os.environ["HTTPS_PROXY"] = self.original_https
        elif "HTTPS_PROXY" in os.environ:
            del os.environ["HTTPS_PROXY"]

        if self.original_all:
            os.environ["ALL_PROXY"] = self.original_all
        elif "ALL_PROXY" in os.environ:
            del os.environ["ALL_PROXY"]

        logger.info("代理已清除")

    def test_proxy(self):
        """测试代理"""
        try:
            # 对于socks代理，使用不同的测试方法
            if self.proxy_type == "socks":
                proxies = {
                    "http": os.environ.get("HTTP_PROXY", ""),
                    "https": os.environ.get("HTTPS_PROXY", ""),
                }
                response = requests.get(
                    "http://httpbin.org/ip", proxies=proxies, timeout=10
                )
            else:
                response = requests.get("http://httpbin.org/ip", timeout=10)

            logger.info(f"proxy test success:{response.json()}")
            return True
        except Exception as e:
            logger.info(f"proxy test failed:{str(e)}")
            self.clear_proxy()
            return False


# 使用示例
if __name__ == "__main__":
    # HTTP代理
    print("=== HTTP代理 ===")
    http_proxy = ProxyManager("http://127.0.0.1:18081", "http")
    http_proxy.test_proxy()

    print("\n=== SOCKS代理 ===")
    socks_proxy = ProxyManager("127.0.0.1:18080", "socks")
    socks_proxy.test_proxy()
