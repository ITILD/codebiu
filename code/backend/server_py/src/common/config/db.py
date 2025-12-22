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
from redis.asyncio import Redis
import logging

logger = logging.getLogger(__name__)

# 关系型数据库(sqlite/postgresql/mysql)
db_rel: DBRelationInterface = None
DaoRel: wraps = None  # 事务管理注解
if conf.db_rel.type:
    db_rel_config: DBConfig = DBEX.get_config(conf.db_rel.type, conf.db_rel)
    db_rel: DBRelationInterface = DBFactory.create_rel(db_rel_config)
    db_rel.connect(is_dev)
    # 增强版异步事务装饰器类
    DaoRel = AsyncTransactional(db_rel.session_factory).transaction

# 缓存数据库(Fakeredis/redis)
db_cache: DBCacheInterface = None
async_cache: Redis = None
if conf.db_cache.type:
    db_cache_config: DBConfig = DBEX.get_config(conf.db_cache.type, conf.db_cache)
    db_cache = DBFactory.create_cache(db_cache_config)
    db_cache.connect(is_dev)
    async_cache = db_cache.async_cache

# 向量化数据库(pymilvus)
db_vector: DBVectorInterface = None

if conf.db_vector.type:
    db_vector_config: DBConfig = DBEX.get_config(conf.db_vector.type, conf.db_vector)
    db_vector = DBFactory.create_vector(db_vector_config)

#  图数据库(neo4j/graph_local)
db_graph: DBGraphInterface = None
if conf.db_graph.type:
    db_graph_config: DBConfig = DBEX.get_config(conf.db_graph.type, conf.db_graph)
    db_graph = DBFactory.create_graph(db_graph_config)
    # db_graph.connect(is_dev)


async def dbs_create_all():
    # 创建所有数据库表
    await db_rel.create_all()


async def dbs_start():
    if conf.state.check_db:
        # 检查版本
        await dbs_create_all()
        # 检查是否有系统表初始化数据
    # 向量数据库连接
    await db_vector.connect()


async def dbs_end():
    # 部分嵌入式数据库存储
    pass
