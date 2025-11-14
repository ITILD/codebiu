from functools import wraps
from common.config.index import conf,is_dev
from common.utils.db.db_factory import DBFactory
from common.utils.db.do.db_config import DBEX, DBConfig
from common.utils.db.session.interface.db_relational_interface import (
    DBRelationInterface,
)
from common.utils.db.session.interface.db_cache_interface import DBCacheInterface
from common.utils.db.utils.async_transactional import AsyncTransactional
from redis.asyncio import Redis
import logging

logger = logging.getLogger(__name__)
# 数据库对象
db_rel: DBRelationInterface = None
# 事务管理注解
DaoRel: wraps = None

if conf.db_rel.type:
    db_rel_config: DBConfig = DBEX.get_config(conf.db_rel.type, conf.db_rel)
    db_rel:DBRelationInterface = DBFactory.create_rel(db_rel_config)
    db_rel.connect(is_dev)
    # 增强版异步事务装饰器类
    DaoRel = AsyncTransactional(db_rel.session_factory).transaction

db_cache: DBCacheInterface = None
async_redis:Redis = None
# redis
if conf.redis.type:
    redis_config: DBConfig = DBEX.get_config(conf.redis.type, conf.redis)
    db_cache = DBFactory.create_cache(redis_config)
    db_cache.connect(is_dev)
    async_redis = db_cache.async_redis
    
    
if __name__ == "__main__":
    from common.config import log
    async def test_redis():
        logger.info("测试")
        try:
            await async_redis.ping()
            logger.info("Redis连接成功")
        except Exception as e:
            logger.error(f"Redis连接失败: {e}")
        # 测试redis set get
        try:
            await async_redis.set("test", "123")
            value = await async_redis.get("test")
            logger.info(f"Redis set get 测试成功: {value}")
        except Exception as e:
            logger.error(f"Redis set get 测试失败: {e}")
    import asyncio
    asyncio.run(test_redis())
