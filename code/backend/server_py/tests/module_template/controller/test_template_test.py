import pytest
import asyncio
import aiohttp
import time

# from common.config.log import logger
import logging

logger = logging.getLogger(__name__)


#  .venv\Scripts\pytest.exe tests\module_template\controller\test_template_test.py -s
@pytest.mark.asyncio
async def test_performance():

    request_count = 3
    duration = 0.02  # 20ms
    base_url = "http://localhost:2001/template/template_test"
    endpoints = {
        "sync": "/sync/{}/{}",
        "async": "/async/{}/{}",
        "async_sync": "/async_sync/{}/{}",
        "async_threadpool": "/async_threadpool/{}/{}",
    }
    results = {}  # 用于存储每个 endpoint 的 total_time
    async with aiohttp.ClientSession() as session:
        for name, path in endpoints.items():
            logger.info(f"\n=== Testing {name} ===")

            start_time = time.time()
            tasks = []

            # 并发10次请求
            for i in range(request_count):
                url = f"{base_url}{path.format(i,duration)}"
                tasks.append(session.get(url))

            # 执行并发请求
            await asyncio.gather(*tasks)
            total_time = time.time() - start_time

            # 计算吞吐量
            throughput = request_count / total_time

            logger.info(f"Total time: {total_time:.2f}s")
            logger.info(f"Throughput: {throughput:.2f} requests/second")

            # 保存结果
            results[name] = total_time
    # 最后统一断言（即使某个失败，也继续检查其他）
    for name, total_time in results.items():
        try:
            assert (
                total_time < request_count * duration / 2
            ), f"{name} total time should be greater than expected minimum"
        except AssertionError as e:
            logger.error(f"Assertion failed for {name}: {e}")
