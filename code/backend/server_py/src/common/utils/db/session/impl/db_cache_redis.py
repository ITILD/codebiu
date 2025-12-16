# DBCacheRedis
from common.utils.db.session.interface.db_cache_interface import DBCacheInterface
from redis.asyncio import Redis as AsyncRedis
from common.utils.db.do.db_config import RedisConfig


class DBCacheRedis(DBCacheInterface):
    """Redis 缓存实现类"""
    async_cache: AsyncRedis = None
    
    def __init__(self, redis_config: RedisConfig):
        """初始化 Redis 缓存连接

        Args:
            host: Redis 主机地址
            port: Redis 端口
            db: Redis 数据库索引
        """
        self.host = redis_config.host
        self.port = redis_config.port
        self.db = redis_config.db
        # 数据库RDB持久化路径
        self.database = redis_config.database

    def connect(self, log_bool=False):
        self.async_cache = AsyncRedis(
            host=self.host,
            port=self.port,
            db=self.db,
        )
        
    # 持久化
    def persist(self):
        self.async_cache.save()
