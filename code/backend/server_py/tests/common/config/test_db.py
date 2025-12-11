import pytest
from src.common.config.db import async_redis
from tests.conftest import setup_logging
import logging
logger = logging.getLogger(__name__)

async def test_redis_connection():
    """测试Redis连接是否正常"""
    logger.info("开始测试Redis连接")
    try:
        await async_redis.ping()
        logger.info("Redis连接成功")
    except Exception as e:
        logger.error(f"Redis连接失败: {e}")
        pytest.fail(f"Redis连接失败: {e}")

@pytest.mark.asyncio
async def test_redis_set_get():
    """测试Redis的set和get操作"""
    logger.info("开始测试Redis set get操作")
    try:
        await async_redis.set("test", "123")
        value = await async_redis.get("test")
        assert value == "123", f"期望值'123'，实际值'{value}'"
        logger.info(f"Redis set get 测试成功: {value}")
    except Exception as e:
        logger.error(f"Redis set get 测试失败: {e}")
        pytest.fail(f"Redis set get 测试失败: {e}")

async def test_redis_operations():
    """综合测试Redis基本操作"""
    # 测试连接
    await async_redis.ping()
    
    # 测试set和get
    test_key = "pytest_test_key"
    test_value = "pytest_test_value"
    
    await async_redis.set(test_key, test_value)
    retrieved_value = await async_redis.get(test_key)
    assert retrieved_value == test_value
    
    # 测试删除
    await async_redis.delete(test_key)
    deleted_value = await async_redis.get(test_key)
    assert deleted_value is None
    
    logger.info("Redis综合操作测试成功")