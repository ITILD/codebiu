# DBCacheFakeredis
from common.utils.db.session.interface.db_cache_interface import DBCacheInterface
from fakeredis import FakeAsyncRedis
from common.utils.db.do.db_config import FakeredisConfig


class DBCacheFakeredis(DBCacheInterface):
    """Fakeredis 缓存实现类"""

    async_cache: FakeAsyncRedis = None

    def __init__(self, redis_config: FakeredisConfig):
        """初始化 Fakeredis 缓存连接

        Args:
            host: Redis 主机地址
            port: Redis 端口
            db: Redis 数据库索引
        """
        # 数据库RDB持久化路径
        self.database = redis_config.database

    def connect(self, log_bool=False):
        """连接 Fakeredis 缓存"""
        self.async_cache = FakeAsyncRedis()

    # 持久化
    def persist(self):
        """将缓存数据持久化到文件"""
        self.async_cache.save()
