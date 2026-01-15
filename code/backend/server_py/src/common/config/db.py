from functools import wraps
from common.config.index import conf, is_dev
from common.utils.db.db_factory import DBFactory
from common.utils.db.do.db_config import DBEX, DBConfig
from common.utils.db.session.interface.db_relational_interface import (
    DBRelationInterface,
)
from common.utils.db.session.interface.db_vector_interface import DBVectorInterface
from common.utils.db.session.interface.db_graph_interface import DBGraphInterface
from common.utils.db.session.interface.db_cache_interface import DBCacheInterface
from common.utils.db.utils.async_transactional import AsyncTransactional

#
from redis.asyncio import Redis
from pymilvus import AsyncMilvusClient
from lancedb import AsyncConnection

import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self):
        self.db_rel: DBRelationInterface | None = None
        self.db_cache: DBCacheInterface | None = None
        self.db_vector: DBVectorInterface | None = None
        self.db_graph: DBGraphInterface | None = None
        # 事务管理注解
        self.DaoRel: wraps | None = None
        # 异步缓存数据库连接
        self.async_cache: Redis | None = None
        # 异步向量数据库连接  注意只能异步连接  生命周期需要运行时获取
        self._async_vector: AsyncConnection | AsyncMilvusClient | None = None
        
    @property
    def async_vector(self) -> AsyncConnection | AsyncMilvusClient | None:
        return self._async_vector
    
    def start(self):
        """初始化所有启用的数据库连接"""
        # 关系型数据库(sqlite/postgresql/mysql)
        if conf.db_rel.type:
            self.db_rel_config: DBConfig = DBEX.get_config(
                conf.db_rel.type, conf.db_rel
            )
            self.db_rel: DBRelationInterface = DBFactory.create_rel(self.db_rel_config)
            self.db_rel.connect(is_dev)
            # 增强版异步事务装饰器类
            self.DaoRel = AsyncTransactional(self.db_rel.session_factory).transaction
        # 缓存数据库(Fakeredis/redis)
        if conf.db_cache.type:
            self.db_cache_config: DBConfig = DBEX.get_config(
                conf.db_cache.type, conf.db_cache
            )
            self.db_cache = DBFactory.create_cache(self.db_cache_config)
            self.db_cache.connect()
            self.async_cache = self.db_cache.async_cache

        # 向量化数据库(pymilvus)
        if conf.db_vector.type:
            self.db_vector_config: DBConfig = DBEX.get_config(
                conf.db_vector.type, conf.db_vector
            )
            self.db_vector = DBFactory.create_vector(self.db_vector_config)
        #  图数据库(neo4j/graph_local)
        if conf.db_graph.type:
            self.db_graph_config: DBConfig = DBEX.get_config(
                conf.db_graph.type, conf.db_graph
            )
            self.db_graph = DBFactory.create_graph(self.db_graph_config)

    async def table_create_all(self):
        # 创建所有数据库表
        await self.db_rel.create_all()

    async def connect_all(self):
        """特殊的连接"""
        # 向量数据库连接
        await self.db_vector.connect()
        self._async_vector = self.db_vector.async_vector

    async def shutdown(self):
        """关闭资源"""
        # if self.db_rel:
        #     await self.db_rel.close()
        # if self.db_cache:
        #     await self.db_cache.close()
        # if self.db_vector:
        #     await self.db_vector.close()
        # if self.db_graph:
        #     await self.db_graph.close()
        pass


# 全局单例
db_manager = DatabaseManager()
db_manager.start()

# 关系型数据库(sqlite/postgresql/mysql)
db_rel: DBRelationInterface = db_manager.db_rel
DaoRel: wraps = db_manager.DaoRel  # 事务管理注解
# 缓存数据库(Fakeredis/redis)
db_cache: DBCacheInterface = db_manager.db_cache
async_cache: Redis = db_manager.async_cache
# 向量化数据库(pymilvus)
db_vector: DBVectorInterface = db_manager.db_vector
#  图数据库(neo4j/graph_local)
db_graph: DBGraphInterface = db_manager.db_graph
