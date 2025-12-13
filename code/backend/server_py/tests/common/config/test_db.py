import pytest
from src.common.config.db import async_redis
# from tests.conftest import setup_logging
import logging
logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_redis_connection():
    """测试Redis连接是否正常"""
    logger.info("开始测试Redis连接")
    try:
        await async_redis.ping()
        logger.info("Redis连接成功")
    except Exception as e:
        logger.error(f"Redis连接失败: {e}")
        pytest.fail(f"Redis连接失败: {e}")
        
    logger.info("开始测试Redis set get操作")
    try:
        await async_redis.set("test", "123")
        value = await async_redis.get("test")
        assert value == "123", f"期望值'123'，实际值'{value}'"
        logger.info(f"Redis set get 测试成功: {value}")
    except Exception as e:
        logger.error(f"Redis set get 测试失败: {e}")
        pytest.fail(f"Redis set get 测试失败: {e}")
        
    logger.info("Redis综合操作测试成功")