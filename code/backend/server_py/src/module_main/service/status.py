import asyncio
from common.utils.cache.cache_ttl import ttl_cache
from common.enum.platform import PlatformId
from common.utils.net.connect.web_connect_test_native import WebConnectTestNative
from common.utils.sys.do.status import HardwareStatus, NetworkStatus
from common.utils.sys.platform import PlatformUtils
from common.utils.sys.status import SystemMonitor
from module_main.do.status import StatusServer
from fastapi import FastAPI
from fastapi.routing import Mount

class StatusService:
    """主机状态服务:采集硬件/网络/平台信息并做短时缓存"""

    def __init__(self):
        """初始化系统监控器与状态缓存"""
        self._monitor = SystemMonitor()  # 实例变量而非类变量
        self._cached_status = None
        self._last_update = 0

    async def hardware_status(self) -> HardwareStatus:
        """采集硬件状态(CPU/内存/磁盘等使用率)"""
        hardware = await self._monitor.get_hardware_status()
        return hardware

    async def sys_info(self) -> PlatformId:
        """获取主机平台信息(系统/厂商/型号)"""
        return PlatformUtils.get_platform_id()

    # network_status
    async def network_status(self, urls: list[str] = None) -> list[NetworkStatus]:
        """并发探测指定URL列表的连通性(默认探测常用站点)

        :param urls: 待探测的URL列表,为空时使用默认列表
        :return: 各URL的连通状态列表
        """
        network_status_list:list[NetworkStatus] = []
        if not urls:
            urls = [
                "https://www.baidu.com",
                "http://example.com",
                "https://github.com",
                "http://www.google.com",
            ]
        tasks = []
        for url in urls:
            task = asyncio.create_task(
                WebConnectTestNative.fetch_title_timeout(url, None, 10)
            )
            tasks.append(task)
        http_results = await asyncio.gather(*tasks, return_exceptions=True)
        for url, result in zip(urls, http_results):
            network_status_list.append(
                NetworkStatus(
                    connect_success=result is not None,
                    url=url,
                )
            )
        return network_status_list

    @ttl_cache(ttl=60) # 缓存一分钟
    async def status_cache(self) -> StatusServer:
        """一分钟一次获取系统状态"""
        hardware = await self.hardware_status()
        network = await self.network_status()
        return StatusServer(hardware=hardware, network=network)
    
    # 查看挂载对象
    async def mount_count(self, app: FastAPI) -> list:
        """列出 app 上所有静态资源挂载路径(用于调试模块挂载)

        :param app: FastAPI应用实例
        :return: 挂载路径列表
        """
        mounts = []
        for route in app.routes:
            if isinstance(route, Mount):
                mounts.append(route.path)
        return mounts
